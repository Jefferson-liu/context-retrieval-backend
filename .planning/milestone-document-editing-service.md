# Milestone: Editable Source Workflow

## Goal
Enable product managers to edit cited passages from the assistant UI, automatically reprocessing embeddings, updating git history, and refreshing impacted answers.

## Dependencies
- Chunk ingestion pipeline with sentence offsets (`chunk_sentences`).
- Git integration for document lifecycle commits.
- Planned queue/executor for background reprocessing jobs.

## Deliverables
- `SourceSnippetService` exposing chunk context (preceding/following sentences, metadata).
- `DocumentEditingService` applying edits, triggering re-chunk/embedding, writing git commits.
- `CitationRefreshJob` to invalidate or regenerate responses referencing updated chunks.
- API endpoints for fetching editable snippets and submitting edits.
- Audit logging for edit operations.

## Data & Schema
- `sentence_revision_history`: captures old/new text, editor, timestamp, related chunk sentence IDs.
- Extend `documents`/`chunks` tables with `last_reprocessed_at`, `edit_source` metadata.
- Enqueue table or utilize existing task queue for reprocessing events keyed by `chunk_id`.

## Services & APIs
- `GET /api/documents/{id}/snippets/{chunk_sentence_id}` → returns snippet payload with context & provenance.
- `POST /api/documents/{id}/snippets/{chunk_sentence_id}` → accepts edits, optional comment, user metadata.
- Background worker (async task) processes edit queue and updates vector store via `VectorStoreGateway`.

## Implementation Steps
1. Define snippet response schema (include doc metadata, sentence context, edit permissions).
2. Implement `SourceSnippetService` with repository helpers for `chunk_sentences`.
3. Implement `DocumentEditingService` to merge edits into source file (line-diff) and stage git commit message.
4. Create background job that reprocesses affected document: re-chunk, re-embed, update vector store(s).
5. Wire `CitationRefreshJob` to mark related `response_segments` as stale and queue regeneration.
6. Add audit logging + notifications for successful edits/failures.
7. Build unit/integration tests for edit flow, git behavior, and queue triggers.

## Testing & Validation
- Unit tests for snippet assembly and diff application (cover overlapping edits, invalid ranges).
- Integration test simulating UI edit: fetch snippet → submit edit → ensure chunk, embedding, git commit updated.
- Regression test verifying query responses refresh with new text.

## Observability
- Metrics: edit success rate, reprocessing latency, queue depth, git commit throughput.
- Alerts on failed reprocessing jobs or stale citation backlog.

## Risks & Mitigations
- **Merge conflicts**: lock snippet while edit in progress or detect conflicting edits via revision IDs.
- **Performance**: batch edits and use background queue; throttle long-running reprocessing jobs.
- **Data loss**: keep snapshot of original text in `sentence_revision_history` for easy rollback.

## Exit Criteria
- UI-driven edit flow works in staging with automatic reprocessing and vector updates.
- Audit trail available for every edit event.
- Documentation updated with API contracts and operational playbook.

## Follow-On Work
- Inline suggestion workflow (proposed edits requiring reviewer approval).
- Real-time diff preview APIs for front-end integration.
