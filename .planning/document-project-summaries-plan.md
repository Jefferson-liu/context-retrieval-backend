# Document & Project Summaries Plan

## Background
- Current ingestion pipeline (`DocumentProcessingService`) stores raw documents, chunks, and chunk embeddings but lacks whole-document or project-level summaries.
- Retrieval relies on chunk embeddings; there is no high-level abstraction for quickly surfacing concise overviews.
- Introducing summaries creates new artifacts that must respect tenant/project scoping and integrate with the existing vector-store abstraction.

## Goals
- Generate and persist a single authoritative summary per document.
- Maintain a tenant/project-scoped project summary that distills the latest document summaries.
- Ensure each summary can participate in semantic retrieval by syncing it into the vector store with a strict 1:1 relationship.
- Provide repositories and services that keep summaries up to date during document ingestion and edits.

## Out of Scope
- Exposing summaries through public API routes (will be handled in a follow-up milestone once storage + refresh loop are stable).
- UI or tooling for manual summary editing.
- Conflict detection between summary text and underlying documents (defer to knowledge graph governance work).

## Data Model
### `document_summaries`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | PK | auto increment |
| `tenant_id` | FK -> `tenants.id` | required for RLS |
| `project_id` | FK -> `projects.id` | matches owning document |
| `document_id` | FK -> `documents.id` | unique; cascade delete |
| `summary_text` | `text` | LLM generated; current snapshot |
| `summary_tokens` | `integer` | optional instrumentation for prompt costs |
| `summary_hash` | `varchar(64)` | fingerprint to avoid redundant regeneration |
| `milvus_primary_key` | `bigint` | mirrors the ID used inside Milvus summary collection |
| `created_at` / `updated_at` | timestamps | default timezone-aware |

Constraints:
- `UNIQUE (document_id)` for 1:1 with documents.
- `CHECK (tenant_id = documents.tenant_id AND project_id = documents.project_id)` enforced via trigger or validated in repository.
- `milvus_primary_key` defaults to `id` unless Milvus requires custom sequencing (store both to simplify migrations).

### `project_summaries`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | PK | auto increment |
| `tenant_id` | FK -> `tenants.id` | required |
| `project_id` | FK -> `projects.id` | unique; 1:1 per project |
| `summary_text` | `text` | aggregated document summary |
| `summary_tokens` | `integer` | cost telemetry |
| `source_document_ids` | `int[]` | provenance of contributing docs |
| `milvus_primary_key` | `bigint` | Milvus identifier for the project summary vector |
| `refreshed_at` | timestamp | last recompute |

### Milvus Collections
- Provision two dedicated Milvus collections via `MilvusCollectionSpec`:
  - `document_summary_vectors`: primary key `summary_id`, fields `tenant_id`, `project_id`, `embedding`.
  - `project_summary_vectors`: primary key `project_summary_id`, fields `tenant_id`, `project_id`, `embedding`.
- Both collections share the global vector dimension (`settings.MILVUS_VECTOR_DIM`) and reuse the HNSW/IP index configuration used elsewhere.
- Collections store no textual data; the Postgres tables remain the source of truth for summary text and metadata.

## Service & Workflow Updates
### Summary Generation
- Add `SummaryGenerator` helper under `infrastructure/ai/` that accepts raw text and returns `(summary_text, token_usage, confidence?)`.
- `DocumentProcessingService.refresh_document` (and any edit workflows) will:
  1. Generate chunk embeddings as today.
  2. Invoke `SummaryGenerator` on cleaned document text.
  3. Upsert into `document_summaries`.
  4. Generate embedding with existing `Embedder` and upsert into the Milvus `document_summary_vectors` collection (using the summary id as primary key).
  5. Submit an async task/event to recompute the parent project summary (to avoid blocking ingestion).

### Project Summary Maintenance
- Introduce `ProjectSummaryService` (services/search or new module) that:
  - Gathers latest document summaries for a project (ordered by recency + importance).
  - Uses `SummaryGenerator` (with prompt tuned for aggregation) to produce project-level summary.
  - Stores text + metadata in `project_summaries`.
  - Generates embedding and upserts into the Milvus `project_summary_vectors` collection.
  - Persists provenance (`source_document_ids`).
- Trigger points:
  - After document summary refresh (debounced queue or scheduled worker).
  - Manual admin endpoint (future) for re-run.

### Vector Store Integration
- Extend `infrastructure/vector_store/factory.py` to expose Milvus-backed gateways for summary collections:
  - `create_vector_store` remains for chunk embeddings (pgvector/Milvus depending on config).
  - New `create_document_summary_store` / `create_project_summary_store` helpers returning `MilvusVectorStore` instances wired to the summary collections.
- Update `MilvusVectorStore` to accept collection name overrides (or create thin subclasses) so summary pipelines reuse connection pooling/index config.
- Ensure summary writes/searches include `tenant_id` + `project_id` fields in Milvus payloads for filtering parity with chunk embeddings.

### Repository Layer
- Create repositories in `infrastructure/database/repositories/`:
  - `DocumentSummaryRepository` for CRUD/upsert operations.
  - `ProjectSummaryRepository` managing project-level records.
- Repositories must set tenant/project context via `ContextScope`.

## Testing Strategy
- Unit tests for repositories verifying tenant scoping and unique constraints.
- Integration tests for `DocumentProcessingService` to confirm summary records are created and Milvus upserts are invoked (mock Milvus gateway + embedder).
- Tests for `ProjectSummaryService` ensuring aggregation handles adds, updates, deletes and pushes vectors to Milvus.
- Milvus search smoke test using embedded/local Milvus or mocked search responses to validate filter expressions and collection routing.

## Observability & Operations
- Log summary generation latency and token counts.
- Add metrics counters for summary refresh successes/failures.
- Plan background job resiliency (retry queue, dead-letter).

## Open Questions
1. Should we store multiple summary revisions or overwrite in place? (Plan assumes overwrite with `summary_hash` to skip redundant writes.)
2. Do project summaries need manual curation hooks before publication?
3. How do we handle very large projects where aggregating every document summary exceeds model context? Potential solution: hierarchical summarization batches.
4. Should summaries participate in standard `SearchService` results immediately or behind feature flag?

## Next Steps
1. Review plan with stakeholders for schema approval.
2. Draft migration + repository scaffolding.
3. Prototype `SummaryGenerator` prompt + integration tests.
4. Wire DocumentProcessingService + ProjectSummaryService flows.
5. Expose admin/test endpoint for reading summaries (post-storage milestone).
