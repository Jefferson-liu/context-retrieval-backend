# Draft: Milvus Prototype Integration

_Last updated: 2025-10-03_

## Objective
Deliver a lean, reversible prototype that lets the backend read/write embeddings to Milvus while keeping pgvector as the default and authoritative store. The prototype must run against the local docker-compose stack (Milvus standalone @ `localhost:19530` with bundled etcd/minio) and stay disabled unless explicitly opted-in via configuration.

## Environment Assumptions
- Compose stack provides:
  - `milvus-standalone`: gRPC port `19530`, default credentials disabled, data volume `./volumes/milvus`.
  - `milvus-minio`: REST ports `9090/9091`, default credentials, volume `./volumes/minio` (implicitly used by Milvus).
  - `milvus-etcd`: internal only, volume `./volumes/etcd`.
- Application and Milvus run on the same host so we can rely on `localhost` connectivity.
- Embedding dimensionality (`EMBEDDING_DIM`) already specified in settings; Milvus schema must match it.
- No TLS/authentication required for the prototype.

## Configuration Additions
- `VECTOR_STORE_MODE` env var (`pgvector` | `milvus` | `dual`). Default `pgvector`.
- Milvus connection settings with sensible defaults:
  - `MILVUS_HOST=localhost`
  - `MILVUS_PORT=19530`
  - Optional `MILVUS_USERNAME`, `MILVUS_PASSWORD` (unused for prototype but wired for future hardening).
- Optional toggle for slow tests: `RUN_MILVUS_TESTS=1`.

## Milvus Store Implementation
1. **Client Wrapper**
  - New `MilvusStore` (`infrastructure/vector_store/milvus_store.py`) implementing `VectorStoreGateway` using `pymilvus`.
   - Connect lazily; raise descriptive error if Milvus unavailable and mode requires it.
2. **Schema Bootstrap**
  - Collection name: `knowledge_chunks`.
   - Fields:
     | Field        | Type        | Notes                         |
     | ------------ | ----------- | ------------------------------ |
     | `chunk_id`   | Int64       | Primary key (1:1 with chunk)  |
     | `tenant_id`  | Int64       | Filterable scalar             |
     | `project_id` | Int64       | Filterable scalar             |
     | `embedding`  | FloatVector | Dimension = embedding model   |
   - Apply IVF_FLAT index with default params (e.g., `nlist=1024`); enable metric `IP` to mirror cosine from embeddings.
3. **Gateway Methods**
   - `upsert_vectors`: use `insert` with `upsert=True` semantics (delete then insert if necessary).
   - `delete_vectors`: filter by `chunk_id` (and tenant/project when included).
   - `search`: restrict by `tenant_id`/`project_id` via Milvus boolean expression (`tenant_id == x && project_id in [...]`).
  - `close`: optional cleanup hook (no-op for now).
4. **Error Handling**
   - Wrap Milvus exceptions; in `dual` mode, log warnings and keep pgvector path alive.

## Milvus Feature Utilisation & Responsibilities
- **Built-in dependencies**: the compose stack already wires etcd (metadata) and MinIO (object storage). We only need to connect to the standalone Milvus endpoint—no extra client code for etcd/minio.
- **Indexes**: IVF_FLAT is the starting index; expose index parameters (e.g., `nlist`) and search params (e.g., `nprobe`) via settings so tuning stays isolated to the store class.
- **Scalar filtering**: use Milvus boolean expressions for `tenant_id` and `project_id` instead of client-side filtering to keep queries efficient.
- **Partitions (later)**: design `MilvusStore` with a helper responsible for partition naming (`tenant_{id}_project_{id}`) so we can add partition management in a follow-up without touching the gateway API.
- **Metric profiling**: keep vector metric (`IP`) configurable for future cosine/L2 experiments.
- **Single responsibility**:
  - `MilvusStore` (under `infrastructure/vector_store/`) handles only gateway methods and delegates bootstrap helpers to a separate `MilvusSchemaManager` module (`infrastructure/vector_store/milvus_schema.py`).
  - Connection management lives in a lightweight `MilvusClientFactory` (`infrastructure/vector_store/milvus_client.py`) that returns a `pymilvus` client; tests can stub this factory.
  - Query builders (e.g., boolean expression strings) reside in dedicated helper functions (`infrastructure/vector_store/milvus_queries.py`) for clarity and reuse.
- **Resource cleanup**: expose optional `close()` or context manager so background jobs can release the client cleanly.

## File Structure Alignment
- `config/settings.py`: extend settings + enums (`VectorStoreMode`, Milvus host/port/user/pass, index/search params).
- `infrastructure/vector_store/__init__.py`: export new factory, store, helpers without breaking existing imports.
- `infrastructure/vector_store/factory.py`: orchestrate mode selection (`PgVectorStore`, `MilvusStore`, optional `DualVectorStore`).
- `services/document/processing.py`, `services/document/editing.py`, `services/queries/query_service.py`, `services/search/search.py`: update to resolve vector store via factory while retaining clean constructor signatures.
- `tests/test_milvus_vector_store.py`: integration test (guarded) that mirrors structure of existing vector store tests for consistency.

## Wiring & Modes
1. Introduce `VectorStoreFactory` to pick implementation based on settings.
2. Update services (`DocumentProcessingService`, `DocumentEditingService`, `SearchService`, `QueryService`) to request the store from the factory instead of directly instantiating `PgVectorStore`.
3. Mode behavior:
   - `pgvector`: current behavior, Milvus ignored.
   - `milvus`: read+write Milvus only (pgvector queries disabled).
4. Ensure DI stays lean (pass context + settings; avoid global state).

## Tooling & Ops
- Provide a simple CLI script `scripts/milvus_healthcheck.py` that attempts to connect and prints collection status; exits non-zero if unreachable.
- Document compose startup snippet and healthcheck command in README or milestone notes.

## Testing Strategy
- Unit tests mocking `MilvusClient` to assert we send the right parameters.
- Integration test (`tests/test_milvus_vector_store.py`) guarded by `RUN_MILVUS_TESTS=1`:
  1. Connect to local Milvus.
  2. Upsert vectors for two tenants.
  3. Query per tenant; expect isolation.
  4. Delete vectors; ensure search returns empty.
- Existing pgvector tests remain mandatory per CI; Milvus tests are optional.

## Observability & Safety
- Log every mode transition (`VectorStoreMode=...`).
- On Milvus errors in dual mode, emit structured warning with chunk IDs; continue pgvector operations.
- Counters (optional for prototype): increment success/failure metrics; fallback to log aggregation if metrics infra not available.

## Rollback Plan
- Set `VECTOR_STORE_MODE=pgvector` (default) to disable Milvus immediately.
- No schema migrations required; pgvector continues as source of truth.
- If Milvus schema corrupts, drop collection via `milvus-standalone` admin or healthcheck script.

## Follow-Ups (post-prototype)
- Partition collections by `(tenant_id, project_id)` for isolation/performance.
- Background reconciliation job comparing Postgres chunks vs Milvus records.
- CLI backfill to pre-seed Milvus from existing embeddings before enabling dual mode.
- Evaluate Milvus auth/TLS once prototype stabilizes.
