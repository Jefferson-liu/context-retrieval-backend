# Implementation Roadmap (Memory Layer Backend)

## Phase 1 – Stabilize Ingestion & Retrieval (Current)
- [x] Document upload, chunking, and embedding pipeline.
- [x] Semantic search with pgvector.
- [x] Automatic git commits for upload/update/delete lifecycle.
- [ ] API contract for external assistant queries (ensure robust error handling & observability).
- [ ] Response payload includes per-segment citations referencing chunk identifiers and offsets.
- [ ] Backfill legacy product docs, generate embeddings, validate recall/precision.
- [ ] Introduce `VectorStoreGateway` abstraction and dual-write flow so we can benchmark Milvus alongside pgvector before cutover.
  - In progress: `PgVectorStore` now drives scoped upserts/search; Milvus driver & dual-write toggle still outstanding.
- [x] Add tenant/project columns to all document + chunk tables and enforce repository-level scoping checks.
  - Implemented via Alembic revision `20251003_multi_tenant_core`, repository refactors, and request-context wiring (`ContextScope`).
  - Runtime RLS + default tenant seeding now configured during app startup (`configure_multi_tenant_rls`, `seed_default_tenant_and_project`).

## Phase 2 – Metadata & Versioning Enrichment
- Extend schema with:
  - `document_versions` (doc_id, version_tag, commit_hash, effective_from, effective_to).
  - `chunk_metadata` (tags, entities, feature flags, confidence).
- Persist git commit metadata alongside document and chunk records.
- Publish ingestion events (e.g., via message bus) for downstream auditing.
- Build CLI/automation to diff new uploads against previous versions and tag major/minor updates.
- Implement `SourceSnippetService` + `DocumentEditingService` to expose editable sentences and apply revisions.
- Store `chunk_sentences` + `response_citations` tables to enable fine-grained editing and traceability.
- Add background reprocessing worker pool + rate limiting to keep edit-triggered re-embeddings performant.
- Introduce PostgreSQL RLS policies and service-layer ACL checks keyed by tenant/project membership (follows the multi-tenant data layer rollout; ensure parity with `.planning/draft-multi-tenant-data-layer.md`).
- Launch `IntentResolverService` MVP that maps queries to the correct project using conversation context + entity aliases.

## Phase 3 – Conflict Detection & Knowledge Assertions
- Introduce `knowledge_assertions` table storing normalized statements with source references and status (active, deprecated, disputed).
- NLP pipeline to extract candidate assertions from chunks (subject-action-object, feature flag states, KPI definitions).
- Conflict detector compares new assertions with active ones (similar subject + contradictory predicate) and raises review tasks.
- Reviewer workflow (API endpoint) to approve replacement, mark outdated, or flag for investigation.
- Manual-first resolution loop: expose conflicting assertion sets via API/UI, capture reviewer decisions, and propagate updates to graph + documents while logging provenance.
- Knowledge graph schema (`knowledge_entities`, `knowledge_assertions`, `knowledge_edges`, `entity_aliases`) built with `(tenant_id, project_id)` partition keys.
- Graph sync jobs keep assertions and entity synonyms current as new documents arrive or edits occur.

## Phase 4 – Quality & Observability
- Metrics: ingestion latency, chunk coverage, retrieval precision@k, conflict resolution SLA.
- Alerts for failed ingestion, stale documents, unresolved conflicts.
- Telemetry for assistant requests -> search hits -> response satisfaction to close the loop.

## Phase 5 – Future Enhancements
- Automated summarization for product epics and release notes.
- Graph-based retrieval combining semantic + relational signals (e.g., dependencies, ownership).
- Multi-tenant support (different product lines with shared infrastructure, isolated knowledge bases).
- Integration with bespoke version control replacing git (domain-aware history, diff visualizations).
