# Milestone: Lean Core Refactor

## Objective
Eliminate non-essential integrations so the retrieval backend focuses on the SAFE + IRCoT trajectory. Simplify the stack to a pgvector-only baseline and remove git mirroring side-effects.

## Success Criteria
- Vector store abstraction targets pgvector exclusively; Milvus code paths and configs are removed or clearly stubbed.
- Document ingestion no longer writes to disk or commits via pygit2; all persistence remains in PostgreSQL.
- Tests/docs reflect the simplified architecture (no Milvus/gitrepo assumptions).
- Service boundaries stay intact (repositories/services) with reduced dependencies and clearer contracts.

## Scope
- Remove Milvus factory, gateway branches, scripts, and tests; keep backward-compatible config toggles documented as deprecated.
- Delete `DocumentFileService` git mirroring and `GitService` usage; prune env variables + tests relying on git.
- Update README + developer docs to describe new baseline.
- Ensure migrations remain valid (no schema change needed, but dependency cleanup may require migration scripts removals or updates).

## Out of Scope
- SAFE/IRCoT controller logic.
- Lexical indexing or sentence hashing.
- Background job infrastructure.

## Deliverables
1. Code cleanup PR removing Milvus + git pathways.
2. Updated tests validating ingestion/query flows using pgvector only.
3. Documentation updates describing the lean architecture.
4. Deprecation notice for removed settings (config defaults, environment variables).

## Dependencies
- None upstream; this milestone unblocks the SAFE + IRCoT workstreams by reducing moving parts.

## Risks & Mitigations
- **Risk**: Removing Milvus may break deployments dependent on it → document migration path and ensure config fallback gracefully errors with actionable message.
- **Risk**: Git removal may affect audit expectations → confirm database + existing logs satisfy provenance requirements and capture gap in backlog if needed.

## Verification Plan
- Run `pytest` suite (vector store + end-to-end smoke tests) ensuring all Milvus-dependent tests are either removed or rewritten.
- Manual API smoke test for `/api/upload` and `/api/query` with sample documents.

## Follow-up Tasks
- Archive Milvus/gitrepo documentation in a separate reference doc if needed.
- Evaluate need for lightweight audit logging replacement post-milestone.
