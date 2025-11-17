# Session Notes – Knowledge Graph / Temporal Pipeline (2025-11-16)

These notes capture the refactor to an event-based KG/temporal pipeline, the prompt/LLM fixes, persistence changes, and remaining issues. Nothing here is speculative—only observed or implemented items.

## LLM / Model infra
- `infrastructure/ai/model_factory.py`: provider inferred from model prefix (claude/anthropic → Anthropic, gpt/text-/o1/openai → OpenAI). Signature allows positional `model_name`. OpenAI chat calls now attach `model_kwargs.metadata={"app": "context-retrieval-backend"}` for tagging. Key selection unchanged.

## Prompt fixes
- All KG prompts import `ChatPromptTemplate` from `langchain_core.prompts`.
- Triplet prompt: examples section kept (per user request); JSON braces escaped to avoid `.format` KeyError. Calls use a variables dict (`{"statement": ...}`) with `DEFAULT_TRIPLET_PROMPT`.
- Date prompt (`prompts/knowledge_graph/date_extraction.py`): `render_inputs` no longer uses string bitwise OR; renders statement fields + optional reference timestamp as bullet text.
- Structured chains call `ainvoke` with mappings, not prompt objects, to avoid `Expected mapping type as input to ChatPromptTemplate`.

## Temporal agent (`services/knowledge/temporal_agent.py`)
- Chains built as prompt → model.with_structured_output; every `ainvoke` gets a variables dict.
- Triplet extraction uses `DEFAULT_TRIPLET_PROMPT` from the prompt module; brace escaping prevents `KeyError("subject_name")`.
- Temporal range extraction returns `TemporalValidityRange`; accesses `valid_at/invalid_at` with `getattr`.
- Guards: if triplet extraction fails, skip creating the event. Statement embeddings set to 768 dims. `chunk_id` accepts int. Entities re-use `entity_idx` so triplet subject/object IDs line up with extracted entities.
- Note: predicates outside the enum (e.g., USES/PROVIDES/INCLUDES) are still dropped, which can skip triplets/events.

## Entity model / resolution
- `schemas/knowledge_graph/entities/entity.py`: `id` can be `int | UUID`; `from_raw` uses `entity_idx` so triplets can reference entities before DB persistence. Event_id field remains in the model.
- `services/knowledge/entity_resolution_service.py`: `canonicalize_batch` upserts extracted entities (normalized name, canonical lookup, create if missing). After the FK issues, new entities are created with `event_id=None` and `resolved_id=None` to avoid FK failures when event rows do not yet exist. Fuzzy clustering (rapidfuzz, thresholds 80/98) assigns `canonical_name`; if a canonical is already claimed, we now avoid unique constraint errors by setting `resolved_id` to the existing canonical owner instead of overwriting `canonical_name`.

## Knowledge service (`services/knowledge/knowledge_service.py`)
- Extraction is event-based: `TemporalKnowledgeAgent.extract_file_events` returns events/triplets/entities. Upload response returns a status dict (`knowledge_result`).
- Entity canonicalization runs before persistence; `name_to_canonical` then backfills triplet `subject_id/object_id` with resolved IDs.
- Invalidations: `batch_process_invalidation` compares incoming FACT, non-atemporal events against existing ones via `fetch_related_triplets_and_events` and `KnowledgeInvalidationService`.
  - If `KNOWLEDGE_AUTO_INVALIDATION` is true, conflicts immediately update existing events via `event_repository.update_invalidation`.
  - If false, creates a pending batch in `knowledge_event_invalidation_batches` (and items) and returns `{"status": "conflicts", "batch_id": ..., "conflicts": [...]}`. New endpoint approves these batches.
- `_persist_event` (not shown in the snippet) writes statements, triplets, entities (upsert), then the event; triplet IDs are stored with the event. Skips persisting when triplet extraction failed.
- `_format_reference_timestamp` ensures ISO with tz; `_parse_timestamp` handles Z.
- Remaining wart: there is a dead block after `return {"status": "success"}` that re-updates invalidations; currently unreachable.

## Invalidation flow
- Services added: `KnowledgeEventRepository` (create/update invalidation), `KnowledgeEventInvalidationBatchRepository` (create/list/mark applied), plus `KnowledgeInvalidationService` still handles statement-level invalidations separately.
- `KnowledgeGraphService.apply_event_invalidation_batch` updates `knowledge_events.invalid_at/invalidated_by` for each batch item and marks the batch applied.
- Statement invalidations (table `knowledge_statement_invalidations`) remain independent from event invalidations—no linkage yet.

## New/changed tables & repos
- `knowledge_events`, `knowledge_event_invalidations`, `knowledge_event_invalidation_batches` (+ batch items). Repos live under `infrastructure/database/repositories/knowledge_event_repository.py` and `knowledge_temporal_repository.py`.
- `knowledge_entities` gained `event_id` (FK to events) and `resolved_id` (self-FK). Event_id is currently left null on upsert to avoid FK violations until event persistence order is reworked.
- `services/knowledge/invalidation_lookup.py` fetches related triplets/events for invalidation checks.

## Router / API
- Upload route returns `knowledge_result` (success or conflicts + `batch_id`).
- New endpoint: `POST /knowledge/event-invalidations/{batch_id}/apply` to approve pending batches (calls `KnowledgeGraphService.apply_event_invalidation_batch`).

## Embeddings
- OpenAI embedding dim standardized to 768 in the embedder and temporal agent; `schemas/knowledge_graph/temporal_event.py` default embedding length updated to 768.

## Migrations (high-signal only)
- Latest files: `20251120_add_knowledge_events_table.py`, `20251121_add_knowledge_event_invalidations.py`, `20251122_add_event_and_resolved_to_entities.py`, `20251123_add_event_invalidation_batches.py`, merge head `20251124_merge_heads.py`, plus drop-guarded `20251115_statement_invalidation_queue.py`. All event/invalidation tables include `DROP TABLE IF EXISTS` to recover from DuplicateTable errors.
- Deleted bad stub `4926bf0db194_.py` (no revision id).
- Multiple-head error resolved via `20251124_merge_heads.py` (revises `20251115_statement_invalidation_queue` + `20251123_event_batches`).
- IMPORTANT: The drop guards will drop and recreate existing tables on rerun—back up production data first. Duplicate table errors during `alembic upgrade head` were due to tables already present; guards were added after those failures.

## Known issues / pending risks
- Predicate coverage: LLM may emit predicates outside enum → triplets/events skipped; consider mapping or extending enum.
- Entities and events: entities are currently upserted with `event_id=None` to dodge FK errors; if you want provenance, add a post-persist update to set `event_id` after events exist.
- Unreachable code: duplicate invalidation update block after the success return in `refresh_document_knowledge`.
- Statement vs event invalidations are decoupled; conflicts in statements do not yet drive event invalidations and vice versa.
- Error history worth remembering:
  - `KeyError("subject_name")` from unescaped braces in triplet prompt (fixed).
  - `TypeError: Expected mapping type as input to ChatPromptTemplate` from passing prompt objects instead of dicts (fixed).
  - `TypeError: unsupported operand type(s) for |: 'str' and 'str'` in date prompt rendering (fixed).
  - `TemporalValidityRange` lacked `.get`, now accessed via `getattr`.
  - `chunk_id` UUID validation error when int; schema now allows int.
  - FK violations on `knowledge_entities.event_id` when event rows missing; mitigated by setting event_id=None on create (but provenance absent).
  - Unique constraint `ix_knowledge_entities_canonical` violated when two entities converged on same canonical; now resolved via `resolved_id` instead of canonical overwrite.

## How to migrate (PowerShell example)
```
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python -m alembic upgrade head
```
If tables already exist, drop guards will recreate them—export data first if needed.

## Key code touchpoints
- Prompts: `prompts/knowledge_graph/*`
- Temporal agent: `services/knowledge/temporal_agent.py`
- Knowledge service: `services/knowledge/knowledge_service.py`
- Entity resolution: `services/knowledge/entity_resolution_service.py`
- Models: `schemas/knowledge_graph/entities/entity.py`, `schemas/knowledge_graph/temporal_event.py`
- Repos: `infrastructure/database/repositories/knowledge_event_repository.py`, `knowledge_temporal_repository.py`, `knowledge_repository.py`
- Migrations: `migrations/versions/2025112*.py` and `20251115_statement_invalidation_queue.py`
