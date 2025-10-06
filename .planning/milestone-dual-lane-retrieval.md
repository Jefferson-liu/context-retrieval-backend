# Milestone: Change-Aware Ingestion & Dual-Lane Retrieval

## Objective
Make ingestion sentence-aware and add lexical retrieval so the system can serve fresh content instantly while maintaining vector-based semantic recall, aligning with SAFE requirements.

## Success Criteria
- Sentence hashing persists only the latest sentence state; ingestion updates only changed sentences.
- Lexical index (Postgres FTS) maintained alongside vector embeddings with consistent tenant/project scoping.
- Fusion retrieval surfaces merged vector + lexical candidates with dedupe and configurable weighting.
- Background embedding queue exists (in-process worker acceptable) to process changed sentences asynchronously.

## Scope
- Add new tables (`document_sentences`, `lexical_index`) and migrations.
- Extend `DocumentProcessingService` (post-refactor) to produce sentence hashes, enqueue changes, and maintain metadata.
- Implement lexical retrieval service + repository with scoring and filtering hooks.
- Introduce fusion layer that runs vector search first, falls back to lexical, and merges results.
- Update API contracts/tests to assert both lanes are exercised.

## Out of Scope
- Full IRCoT reasoning loop.
- External job queue infrastructure (e.g., Celery); we will leverage asyncio background tasks for now.
- UI or API changes beyond ensuring `/api/query` returns merged search results to the controller.

## Deliverables
1. Database migration scripts and models for sentence storage.
2. Updated ingestion pipeline with diff-aware processing and lexical index maintenance.
3. Fusion retrieval module with unit/integration tests.
4. Background task runner or service stub for delayed embeddings + metrics for queue depth.

## Dependencies
- Completion of Lean Core Refactor (baseline simplified to pgvector-only, no git side-effects).

## Risks & Mitigations
- **Risk**: Sentence hashing adds latency to uploads → use async executor + chunked processing, measure and optimize.
- **Risk**: Lexical index rebalancing may conflict with transactions → ensure operations run within FastAPI-managed session or dedicated connection.
- **Risk**: Fusion scoring needs tuning → expose configuration and capture metrics for evaluation milestone.

## Verification Plan
- Unit tests for hashing, sentence diffing, and lexical search.
- Integration test uploading doc revisions to confirm only changed sentences re-embed.
- Query tests verifying lexical fallback returns results when vector similarity is low.

## Follow-up Tasks
- Expose instrumentation for backlog age and retrieval mix (vector vs lexical).
- Evaluate need for external queue once workload increases.
