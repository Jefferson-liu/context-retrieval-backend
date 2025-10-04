# Milestone: Structured Query Responses with Citations

## Goal
Return answers that include sentence-level segments mapped to chunk citations, enabling UI highlighting and audit trails.

## Dependencies
- `QueryService` logging queries and returning raw chunks.
- Access to LLM provider through `AnswerComposerService` (to be created/extended).
- Planned tables `response_citations`, `chunk_sentences` for fine-grained attribution.

## Deliverables
- Updated schema: `response_segments`, `response_citations`, `chunk_sentences`.
- `AnswerComposerService` that takes ranked chunks and produces `{text, segments[]}`.
- Enhanced `POST /api/query` contract returning structured payload.
- Persistence logic to store segments + citations per response.
- Unit & integration tests covering happy path and edge cases (no citations, partial matches).

## Data & Schema
- `chunk_sentences`: `id`, `chunk_id`, `tenant_id`, `project_id`, `start_char`, `end_char`, `text`.
- `response_segments`: `id`, `response_id`, `order`, `text`.
- `response_citations`: `id`, `segment_id`, `chunk_sentence_id`, `confidence`.
- Migrations ensure tenant/project columns exist and are indexed.

## Services & APIs
- Extend `QueryService` to orchestrate sentence extraction before calling LLM.
- Add `CitationAssembler` helper to map LLM-provided offsets to sentences.
- API schema updates in `schemas/responses/query.py` (or equivalent) and docs.

## Implementation Steps
1. Add schema migrations + SQLAlchemy models for new tables.
2. Populate `chunk_sentences` during ingestion (LangChain splitter or spaCy).
3. Implement `AnswerComposerService` (prompt template, LLM call, fallback on failure).
4. Create citation mapping utility aligning answer segments to sentences.
5. Update API endpoint to return structured payload and persist data.
6. Write unit tests for mapping logic + LLM mock.
7. Update Postman/OpenAPI examples.

## Testing & Validation
- Unit tests for sentence splitting, citation mapping, schema interactions.
- Integration test hitting `/api/query` with seeded data verifying response shape.
- Regression test ensuring old clients (if any) still function or versioned endpoint.

## Observability
- Metrics: LLM latency, citation coverage %, sentences per response.
- Log warnings when mapping fails or confidence < threshold.

## Risks & Mitigations
- **LLM hallucination** → enforce answer segments only from provided chunks; consider constrained prompting.
- **Sentence alignment drift** → store original offsets, add checksum to detect chunk edits.

## Exit Criteria
- Query endpoint returns structured payload in staging.
- Citations visible in UI prototype with highlight support.
- Docs + SDKs updated to consume new shape.

## Follow-On Work
- Add multilingual support for sentence splitting.
- Explore summarization segments for long answers.
