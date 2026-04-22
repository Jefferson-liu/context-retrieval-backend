# Repo Knowledge Ingestion – Technical Debt

## Parser Fidelity
- Tree-sitter extraction is intentionally best-effort and heuristic-based.
- Symbol resolution currently prefers local file symbols and first-match global symbol lookups; ambiguous references can map imperfectly.
- Reference edges in TS/JS can be noisy because identifier-level extraction is broad.
- TS/JS call-edge extraction now skips complex non-identifier call targets to avoid oversized external reference identities; this improves stability but may reduce recall for dynamic invocation patterns.

## Source Adapters
- `git_url` adapter is contract-defined but not implemented.
- No clone/auth/cache strategy exists yet for remote repositories.

## Background Execution
- Runner is in-process only (no persistent queue); runs are marked failed on process restart.
- No priority scheduling or rate limiting beyond worker concurrency.
- Pipeline orchestration runner is also in-process and keyed by source run id; if the process restarts, orchestration intent is not persisted and users must re-trigger pipeline orchestration.
- `force_reingest` is currently a queue-time control (not persisted on `repo_runs`), so the force intent is lost if the process restarts before the queued ingestion run executes.

## Testing Debt
- Added unit tests for discovery/chunking/parser registry/import helper logic.
- Full integration tests (API + DB + worker lifecycle + mixed-language repo fixtures) are still missing.
- Runtime strict parser checks currently fail in WSL when `tree_sitter_language_pack` and/or `langchain_text_splitters` are missing from the active interpreter.
- Added file-summary unit tests (summarizer + context assembler), but API/DB integration tests for file-summary runs are still missing.
- Added repo-full-summary unit tests (tool lookup + markdown envelope parsing), but API/DB integration tests for repo-full-summary run/readme endpoints are still missing.
- Windows venv runtime checks for new summary pipeline are intermittently blocked from WSL by `UtilBindVsockAnyPort` transport failures.
- Added embedding/retrieval helper unit tests, but API/DB integration tests for embedding runs and context-pack endpoint are still missing.
- Added Repo Manager and architecture unit tests, but API/DB integration tests for the canonical repo-manager endpoints, merged architecture endpoint, per-segment Mermaid persistence, and any retained compatibility-layer `group-summary` endpoints are still missing.
- Added `GET /repo-knowledge/runs` source+file-summary linkage endpoint, but dedicated API contract tests for this list shape/order/filtering are still missing.
- Added run-selector flexibility for file-summary/embedding create payloads, but API integration tests for mixed selector inputs (`repo_run_id` only, dual-selector mismatch) are still missing.
- Added pipeline endpoints (`POST/GET /repo-knowledge/pipeline-runs`) and stage-resolution helper tests, but API/DB integration tests for full chained orchestration are still missing.
- Added file-summary diagnostics listing endpoint (`GET /repo-knowledge/file-summary-runs/{file_summary_run_id}/diagnostics`), but API integration tests for filtering/pagination are still missing.
- Runtime tests currently rely on invoking the Windows project venv from WSL with escalated execution; local Linux test environment is not provisioned with required dependencies.

## Data/Retention
- Duplicate detection currently marks status by fingerprint but does not deduplicate stored file/chunk/edge rows across runs.
- No retention policy or cleanup job for historical runs is implemented yet.
- Startup schema migration currently focuses on table/column rename/copy safety and does not normalize legacy index/constraint names; follow-up migration tooling is still needed for full DDL cleanup.
- File-summary runs store per-run artifacts in `repo_file_summaries`; no compaction/retention policy exists for repeated re-runs.
- Repo-full-summary runs store README artifacts in `repo_full_summaries`; no retention/compaction policy exists for stale repo README outputs.
- Embedding runs store per-run vectors in `repo_embeddings`; no retention/compaction policy is implemented for stale embedding runs.
- Repo Manager/architecture runs store artifacts in `repo_manager_*` tables; no retention/compaction policy is implemented for stale/obsolete runs.
- External subject identity still uses raw-text unique constraints in `repo_subjects`; runtime now hashes oversized refs before insert, but schema-level identity should migrate to explicit hash-key columns to fully remove index-size sensitivity.
- `RepoSubjectRepository.get_or_create_external(...)` is still select-then-insert (non-atomic) and can hit unique-key races under concurrent ingestion transactions; pipeline duplicate-enqueue paths were reduced, but repository-level upsert semantics should still be hardened.
- `repo_subjects` uniqueness currently depends on nullable columns (`symbol_qualname`, `external_ref`) under PostgreSQL null semantics, so duplicate logical identities can still accumulate. Runtime reads are now duplicate-tolerant, but a schema migration + one-time dedup cleanup is still required for full integrity.

## Summary Quality / Prompting
- Prompt quality is baseline and has not yet been benchmarked against architecture-level task quality.
- Prompts are now loaded strictly from `services/repo_knowledge/prompts/*.md` with no code fallback constants; missing/empty files fail fast at runtime, so deployment packaging must include prompt files.
- File summarization now uses LangGraph ReAct + LangChain tools with filesystem + graph tools, but quality/cost/latency benchmarks are not yet calibrated per repo size.
- Repo full-summary generation now uses LangGraph ReAct + LangChain tools with filesystem/graph/file-summary tools, but README quality/cost/latency benchmarks are not yet calibrated per repo size.
- ReAct Gemini compatibility currently depends on pinned package versions; CI does not yet enforce an explicit lockfile install path beyond `requirements.txt` and `requirements-repo-knowledge-agent-constraints.txt`.
- No automated live-provider smoke test exists in CI to catch future Gemini tool-calling protocol regressions early.
- Repo full-summary still leaves `entry_points_trace` and `related_repo_info` empty; this means the new architecture stage does not yet receive the paper's full Algorithm 1 context.
- `return_file_code(...)` currently relies on suffix-based fuzzy file resolution when exact relative path lookup fails; this can be ambiguous in repos with repeated filenames.
- `return_file_summary(file_name)` currently resolves suffix collisions by shortest path + lexical ordering, which can pick the wrong file in heavily duplicated trees.
- Reference-graph lookups for `class`/`func` still use best-effort first-match symbol resolution and can select the wrong symbol when names are duplicated.
- Neighbor selection currently uses a fixed per-direction cap; no centrality or relevance ranking is applied yet.
- Business-focused reranking currently relies on single-pass Gemini JSON output with lightweight fallback; no offline quality benchmark exists yet for ranking accuracy.
- Symbol hints are derived from best-effort AST edges and may include noisy `references` edges.
- The Repo Manager uses dependency-aware balanced segmentation with estimated token counts rather than a true tokenizer-backed budget; segment boundaries are still approximate.
- Repo Manager/architecture artifacts now use canonical `repo_manager` API/module/storage naming end-to-end. A formal Alembic migration is still needed to rename legacy DB tables/indexes.
- Infrastructure detection in architecture segments is token-heuristic based and not yet calibrated against labeled corpora.
- Segment and merge failures now persist structured LLM diagnostics, but file-summary/repo-full-summary should eventually converge on the same shared error envelope for perfect cross-stage consistency.

## MCP Surface Debt
- MCP tooling is currently read-only and intentionally does not expose write/update operations.
- MCP scope resolution currently relies on explicit `tenant_id`/`user_id` arguments or placeholder defaults; token-based identity propagation for MCP sessions is not yet implemented.
- MCP tools reuse paginated repository queries and do not yet provide a single "full dump export" with stable continuation tokens.
- MCP tooling now exposes repo-manager terminology for segment inspection with canonical `repo_list_repo_manager_segments` / `repo_read_repo_manager_segment` tools.
