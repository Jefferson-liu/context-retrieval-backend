# Draft: Lean Core Refactor

## Goals
- Remove Milvus dependency while keeping pgvector functional.
- Excise git mirroring side-effects (`DocumentFileService`, `GitService`).
- Stabilize ingestion/query flows with slimmer dependency surface.

## Implementation Steps
1. **Config Cleanup**
   - Remove `VECTOR_STORE_MODE` toggles referencing Milvus; default to `pgvector`.
   - Delete Milvus-related settings/env parsing.
   - Update factory to raise a clear error if non-pgvector is requested.
2. **Vector Store Layer**
   - Delete `infrastructure/vector_store/milvus` package and tests.
   - Inline pgvector gateway as the single implementation; simplify interfaces where over-generalized.
   - Update scripts/tests referencing Milvus (e.g., `scripts/milvus_*`, `tests/test_milvus_*`).
3. **Document Persistence**
   - Remove `DocumentFileService` and `GitService` usages from `DocumentProcessingService`.
   - Delete service modules, config flags, and tests.
   - Drop related requirements (`pygit2`).
4. **Docs & README**
   - Update README to remove Milvus/gitrepo instructions.
   - Add migration note for teams previously using Milvus (link to archived doc).
5. **Dependency/Env Review**
   - Update `requirements.txt` to remove unused packages.
   - Purge `.env.example` entries if present (create if missing).

## Schema & Data Impact
- No database migrations needed.
- Ensure removing Milvus does not leave orphaned config tables or metadata.

## Testing Strategy
- Run `pytest` suite after cleanup.
- Manual smoke: upload + query to validate baseline still works.
- Verify no import errors when `VECTOR_STORE_MODE` env is absent.

## Rollback Plan
- Retain Milvus code in tagged release `v0.1-milvus` for reference.
- If refactor introduces regressions, revert to previous commit while we triage.

## Open Questions
- Do we need an alternative for git-based audit trail? (Track in backlog.)
- Should we preserve CLI scripts for Milvus as archived docs instead of source code? (Decision pending.)
