# Draft: Change-Aware Ingestion & Dual-Lane Retrieval

## Goals
- Detect changed sentences during ingestion and update storage/indexes incrementally.
- Maintain lexical search alongside vector embeddings.
- Provide fused retrieval outputs to downstream SAFE controller.

## Implementation Steps
1. **Schema & Models**
   - Create migrations for `document_sentences` (id, document_id, sentence_index, content, content_hash, tenant_id, project_id, updated_at) capturing only the latest state.
   - Add lexical index table or Postgres `tsvector` column with GIN index for full-text search.
   - Update SQLAlchemy models/repositories accordingly.
2. **Sentence Extraction Pipeline**
   - Introduce `SentenceExtractor` utility (markdown-aware) producing normalized text + hash.
   - Modify `DocumentProcessingService` to:
     - Split incoming content into sentences.
     - Compare hashes with existing entries.
     - Persist new/changed sentences and mark removed ones.
   - Set `chunk_id` / `doc_id` references in dependent tables to `NULL` when sentences are removed so citations degrade gracefully.
     - Enqueue changed sentences for embedding regeneration.
3. **Embedding Queue Stub**
   - Implement in-process queue (asyncio `Queue`) with worker task started at app startup.
   - Worker batches sentences, calls embedding model, and upserts vectors (reusing `VectorRecord`).
   - Add metrics counters (basic logging for now).
4. **Lexical Retrieval Service**
   - Build `LexicalSearchRepository` using Postgres FTS (`tsvector`) with ranking (`ts_rank_cd`).
   - Ensure tenant/project filters applied.
   - Write tests covering OR/AND queries, phrase search, and scoring.
5. **Fusion Layer**
   - Create `FusionRetriever` combining vector + lexical results:
     - Run vector search first (top_k configurable).
     - If insufficient matches or low scores, run lexical search.
     - Merge on `(document_id, chunk_id?, sentence_id)` with score blending.
   - Return unified `RetrievedContext` objects for controller.
6. **Query Service Integration**
   - Update `QueryService` to call the fusion layer and return both vector + lexical evidence.
   - Adjust tests to mock lexical service when needed.

## Testing Strategy
- Unit tests for sentence hashing (repeat ingestion, edit, removal).
- Integration test uploading modified doc and verifying only changed sentences re-embedded.
- Fusion tests covering vector success, lexical fallback, and dedupe logic.

## Rollout Plan
- Ship behind feature flag `ENABLE_DUAL_RETRIEVAL` defaulting to true after smoke tests.
- Provide migration instructions in README / ops doc.

## Open Questions
- How to store lexical index: same table vs separate? (Default: `documents` with new `tsvector` column.)
- Should we keep chunk-level embeddings in addition to sentence-level? (Initial plan: yes, reuse chunks for compatibility until SAFE controller fully sentence-based.)
