# Vector Store – Technical Spec

## Core Responsibility
Store and search chunk embeddings for semantic retrieval, scoped by tenant/project/user, with pluggable backends (pgvector or Milvus).

## Factory & Interfaces
- `infrastructure/vector_store/factory.create_vector_store`:
  - Chooses backend via `VECTOR_STORE_MODE` (config) or explicit override.
  - Supported backends: `pgvector`, `milvus`.
- `infrastructure/vector_store/gateway.VectorStoreGateway`:
  - Methods: `upsert_vectors(records)`, `delete_vectors(chunk_ids, tenant_id, project_id)`, `search(query_embedding, tenant_id, project_ids, user_id, top_k)`.
- `VectorRecord`: chunk_id, embedding, tenant_id, project_id.

## PgVector Backend
- File: `infrastructure/vector_store/pgvector_store.py`
- Stores embeddings in `embeddings` table with tenant/project columns.
- Upsert via `INSERT ... ON CONFLICT (chunk_id) DO UPDATE` to keep tenant/project aligned.
- Search: cosine distance (`1 - distance` as similarity), joins `chunks` + `documents`; filters by tenant_id, project_ids, and `documents.created_by_user_id == user_id`.
- Deletes by chunk_id with tenant/project filters when provided.

## Milvus Backend
- File: `infrastructure/vector_store/milvus/milvus_store.py`
- Ensures collection exists with HNSW index, IP metric; vector dim from settings.
- Upsert: delete existing chunk_ids then insert embeddings.
- Search: builds filter `tenant_id == X && project_id in [...]`; fetches chunks+docs (also filtered by user_id).
- Delete: removes embeddings by chunk_ids.

## Tenancy & Security
- All searches require tenant_id and project_ids; user_id filter applied in both backends (document ownership).
- Vectors carry tenant_id/project_id in the stored records; deletions require matching scope.

## Performance Notes
- Pgvector search orders by cosine distance; Milvus uses HNSW with configurable ef.
- Embedding dimension must match settings; mismatch raises errors.
- Concurrency managed at caller level (ingestion uses semaphores).

## Gaps / TODO
- No rate limiting/backpressure built into the gateway.
- No vector cache or warmup; index rebuild path not defined for model changes.
- Milvus collection/index parameters are static; no per-tenant collections.
