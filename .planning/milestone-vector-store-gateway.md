# Milestone: Vector Store Gateway & Milvus Dual-Write

_Active draft: `.planning/draft-milvus-prototype.md` captures the current lean integration plan and maps each step to the existing repo structure (`config/`, `infrastructure/vector_store/`, `services/`, `tests/`)._

## Goal
Build a storage-agnostic vector interface that supports pgvector today and Milvus tomorrow without code churn in retrieval services. This unlocks dual-writing, benchmarking, and an eventual cutover.

## Dependencies
- Existing `SearchRepository.semantic_vector_search` implementation.
- Document ingestion pipeline producing `(chunk_id, embedding)` pairs.
- Configuration management through `config/settings.py`.

## Deliverables
- `VectorStoreGateway` interface specifying CRUD/search contracts.
- `PgvectorStore` implementation wired to current tables.
- `MilvusStore` stub (connectivity, schema bootstrap, upsert/search/delete) behind feature flag.
- Background reconciliation job to ensure chunk ↔ vector parity.
- Integration tests covering dual-write + failover scenarios.

## Data & Schema
- Maintain 1:1 mapping between `chunks` and vectors; Milvus primary key mirrors `chunk_id`.
- Milvus collections partitioned by `(tenant_id, project_id)`.
- Migration script to backfill Milvus with existing vectors when the flag is enabled.

## Services & APIs
- Inject gateway into `DocumentProcessingService` and `QueryService` via dependency container.
- Gateway exposes `upsert_vectors`, `delete_vectors`, `search`, `healthcheck`.
- Feature flag (`VECTOR_STORE_MODE=pgvector|dual|milvus`) toggles behavior.

## Implementation Steps
1. Define gateway protocol (abstract base or Protocol class).
2. Refactor pgvector code behind new gateway.
3. Implement Milvus client wrapper (init collection, ensure index, handle partitions).
4. Wire ingestion to call both stores when mode=dual.
5. Update retrieval flow to choose store based on mode.
6. Build reconciliation worker that compares chunk ids vs. vector ids and repairs drift.
7. Provide admin CLI/endpoint to trigger backfill or healthcheck.

## Lean Prototype Plan (2025-10-03)
**Goal:** add a Milvus-backed `VectorStoreGateway` option without disturbing the pgvector happy path. Prototype should run against the local `docker-compose` stack (standalone Milvus on `localhost:19530`, bundled etcd/minio) and remain off by default.

### Assumptions
- Compose stack is launched separately; app only needs the Milvus gRPC endpoint (`localhost:19530`).
- Default Milvus authentication is disabled; proto flow sticks with anonymous access.
- Embedding dimensionality matches our current model (from config).

### Scope (lean)
1. **Configuration**
	- Add `MILVUS_HOST`, `MILVUS_PORT`, `VECTOR_STORE_MODE` to `config/settings.py`. Default mode stays `pgvector`.
	- Optional env to control prototype tests (`RUN_MILVUS_TESTS=1`).

2. **MilvusStore (minimal)**
	- Implement `MilvusStore` alongside `PgVectorStore` using `pymilvus`.
	- On init: connect, create collection `knowledge_chunks` if missing, schema fields:
	  - `chunk_id` (Int64, primary key)
	  - `tenant_id` (Int64)
	  - `project_id` (Int64)
	  - `embedding` (FloatVector, dim from settings)
	- Apply IVF_FLAT index w/ default params; skip partitions for prototype (scope later).
	- Implement CRUD methods mirroring `VectorStoreGateway` using simple filters on `tenant_id`/`project_id`.

3. **Gateway wiring**
	- Add a factory (e.g., `get_vector_store(db, settings, context)`) returning `PgVectorStore`, `MilvusStore`, or `DualVectorStore` (pgvector + Milvus) based on mode.
	- Update services (`DocumentProcessingService`, `DocumentEditingService`, `QueryService`, `SearchService`) to consume the factory; pgvector remains default so existing behavior unchanged.
	- Dual mode (if enabled) simply writes to both stores but still searches pgvector for now.

4. **Bootstrap & teardown tooling**
	- Provide a lightweight script `scripts/milvus_healthcheck.py` to verify connectivity; not required in production path but helps local setup.
	- Document compose command and healthcheck in README planning.

5. **Testing**
	- Add integration test that runs only when `RUN_MILVUS_TESTS=1` and Milvus is reachable (skip otherwise). Test: upsert two vectors, query, ensure tenant filter works.
	- Existing pgvector tests unchanged.

6. **Observability / Safety**
	- Log warnings (not exceptions) when Milvus writes fail in dual mode; continue pgvector path to avoid outages.
	- Expose basic metrics counters (`milvus_upserts_total`, `milvus_failures_total`) if instrumentation is available; otherwise log counts at INFO for prototype.

### Out of Scope for Prototype
- Automated reconciliation worker.
- Milvus partitioning per tenant/project (tracked for full milestone).
- Production-ready index tuning, TLS/auth, or HA deployment.
- CLI backfill (manual script acceptable later).

### Rollback
- Set `VECTOR_STORE_MODE=pgvector` (default) or unset Milvus env vars to disable prototype instantly.
- No schema migrations required—pgvector tables remain the source of truth.

## Testing & Validation
- Unit tests using Milvus mock/docker container covering insert/search/delete.
- Integration test: ingest document → ensure vector exists in both stores.
- Failure simulation: drop Milvus connection; verify pgvector path still works when mode=dual.
- Load test command to benchmark latency deltas.

## Observability
- Metrics: upsert latency, search latency, reconciliation drift count.
- Logging for collection creation/indexing events.
- Alert when dual-write delta exceeds threshold.

## Risks & Mitigations
- **Milvus downtime** → keep pgvector authoritative until cutover.
- **Schema divergence** → reconciliation + nightly sanity checks.

## Exit Criteria
- Dual-write mode stable in staging with clean reconciliation reports.
- Documentation updated with deployment/config steps.
- Operators know how to monitor and recover from Milvus issues.

## Follow-On Work
- Evaluate multi-replica Milvus deployment for HA.
- Explore hybrid search (vector + scalar filters) once Milvus is default.
