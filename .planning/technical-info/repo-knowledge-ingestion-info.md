# Repo Knowledge Ingestion – Technical Spec

## Core Responsibility
Ingest repository files from local paths into run-scoped relational tables, chunk file contents with LangChain, build AST-derived dependency edges (file-level + symbol-level) using Tree-sitter for Python/TypeScript/JavaScript, run asynchronous LLM-based file-summary extraction over ingested artifacts, generate a repo-level README-style full summary, then run an ArchAgent-inspired Repo Manager plus architecture stage that produces balanced dependency-aware segments and merged Mermaid architecture diagrams before embedding-driven retrieval consumers use the artifacts.

## API Entry Points
- `POST /repo-knowledge/runs`
  - Queues an asynchronous ingestion run.
  - Supports `source_type=local_path`; `git_url` currently returns `501`.
  - Optional control:
    - `force_reingest` (bypasses final `skipped_duplicate` status marking for the run).
- `GET /repo-knowledge/runs`
  - Lists scoped source ingestion runs with linked file-summary run IDs/statuses.
  - Supports pagination (`limit`, `offset`) and optional status filter (`status`).
- `GET /repo-knowledge/runs/{run_id}`
  - Returns run status and counters.
- `GET /repo-knowledge/runs/{run_id}/files`
  - Lists per-file snapshot metadata and parse status.
- `GET /repo-knowledge/runs/{run_id}/edges`
  - Lists dependency edges with optional filters.
- `POST /repo-knowledge/file-summary-runs`
  - Queues an asynchronous file-summary run for a completed ingestion run.
  - Request fields:
    - selector (one required): `source_run_id` or `repo_run_id`
    - control: `force_refile_summary`
- `GET /repo-knowledge/file-summary-runs/{file_summary_run_id}`
  - Returns file-summary run status and counters.
- `GET /repo-knowledge/file-summary-runs/{file_summary_run_id}/summaries`
  - Lists generated summary artifacts.
- `GET /repo-knowledge/file-summary-runs/{file_summary_run_id}/diagnostics`
  - Lists per-file diagnostics captured during file summarization failures (with subject path + diagnostic details).
- `GET /repo-knowledge/runs/{run_id}/file-summaries/latest`
  - Returns latest completed file summaries for a source ingestion run.
- `POST /repo-knowledge/repo-full-summary-runs`
  - Queues an asynchronous repo-level README full-summary run from a completed file-summary run.
  - Request fields: `source_file_summary_run_id`, `force_rerepo_summary`.
- `GET /repo-knowledge/repo-full-summary-runs/{repo_full_summary_run_id}`
  - Returns repo full-summary run status and counters.
- `GET /repo-knowledge/repo-full-summary-runs/{repo_full_summary_run_id}/readme`
  - Returns canonical markdown README artifact for the run.
- `GET /repo-knowledge/runs/{run_id}/repo-full-summary/latest`
  - Returns latest completed repo full-summary README for a source ingestion run.
- `POST /repo-knowledge/embedding-runs`
  - Queues an asynchronous embedding run from a completed file-summary run.
  - Request fields:
    - selectors (at least one required): `source_file_summary_run_id` or one of `source_run_id`/`repo_run_id`
    - control: `force_reembed`
  - Resolution behavior:
    - if `source_file_summary_run_id` is provided, that run is used directly.
    - if only `source_run_id`/`repo_run_id` is provided, the latest completed file-summary run for that source run is selected.
    - if both file-summary and source selectors are provided, they must refer to the same source run.
- `GET /repo-knowledge/embedding-runs/{embedding_run_id}`
  - Returns embedding run status and counters.
- `GET /repo-knowledge/embedding-runs/{embedding_run_id}/items`
  - Lists embedding metadata rows (vector payload is not exposed).
- `POST /repo-knowledge/runs/{run_id}/context-pack`
  - Builds a business-focused context pack from repo summary embeddings + dependency graph expansion.
- `POST /repo-knowledge/repo-manager-runs`
  - Queues an asynchronous Repo Manager plus architecture run from a completed file-summary run.
  - Canonical request fields: `source_file_summary_run_id`, `force_rerepo_manager`.
  - Compatibility note: the underlying storage layer still uses legacy `group_summary` repositories/tables.
- `POST /repo-knowledge/pipeline-runs`
  - Creates a source ingestion run from `source_path` and orchestrates downstream file-summary -> repo-full-summary -> embedding -> grouping/group-summary automatically.
  - Uses the source ingestion `run_id` as the pipeline identifier (no separate pipeline id/table).
  - Optional force controls:
    - `force_reingest`
    - `force_refile_summary`
    - `force_rerepo_summary`
    - `force_reembed`
    - `force_rerepo_manager`
- `GET /repo-knowledge/pipeline-runs/{run_id}`
  - Returns aggregate pipeline status/stage keyed by source ingestion `run_id`.
  - Includes linked stage run ids/statuses:
    - file-summary run
    - repo-full-summary run
    - embedding run
    - Repo Manager/architecture run (`repo_manager_run_id`)
  - Stage values:
    - `ingestion`
    - `file_summary`
    - `repo_full_summary`
    - `embedding`
    - `repo_manager`
    - `architecture`
    - terminal: `completed` / `failed`
- `GET /repo-knowledge/repo-manager-runs/{repo_manager_run_id}`
  - Returns Repo Manager/architecture run status and counters.
- `GET /repo-knowledge/repo-manager-runs/{repo_manager_run_id}/segments`
  - Lists Repo Manager segments + per-segment architecture payloads + optional members.
- `GET /repo-knowledge/repo-manager-runs/{repo_manager_run_id}/architecture`
  - Returns the merged repo-level Mermaid architecture diagram for the run.
- `GET /repo-knowledge/runs/{run_id}/repo-manager/latest`
  - Returns latest completed Repo Manager segment artifacts for a source ingestion run.

## Key Components
- Router:
  - `routers/repo_knowledge_router.py`
  - `routers/repo_knowledge_file_summary_router.py`
  - `routers/repo_knowledge_repo_full_summary_router.py`
  - `routers/repo_knowledge_embedding_router.py`
  - `routers/repo_knowledge_group_summary_router.py` (legacy compatibility surface)
  - `routers/repo_knowledge_repo_manager_router.py` (canonical surface)
  - `routers/repo_knowledge_pipeline_router.py`
- Services:
  - `services/repo_knowledge/ingestion_service.py`
  - `services/repo_knowledge/background_runner.py`
  - `services/repo_knowledge/discovery_service.py`
  - `services/repo_knowledge/chunking_service.py`
  - `services/repo_knowledge/sources/*`
  - `services/repo_knowledge/parsing/*`
  - `services/repo_knowledge/file_summary_service.py`
  - `services/repo_knowledge/file_summary_background_runner.py`
  - `services/repo_knowledge/repo_full_summary_service.py`
  - `services/repo_knowledge/repo_full_summary_background_runner.py`
  - `services/repo_knowledge/summarization/*`
  - `services/repo_knowledge/repo_full_summarization/*`
  - `services/repo_knowledge/embedding_service.py`
  - `services/repo_knowledge/embedding_background_runner.py`
  - `services/repo_knowledge/embeddings/*`
  - `services/repo_knowledge/retrieval/*`
  - `services/repo_knowledge/group_summary_service.py` (legacy-named implementation)
  - `services/repo_knowledge/group_summary_background_runner.py` (legacy compatibility runner)
  - `services/repo_knowledge/repo_manager_service.py` (canonical surface wrapper)
  - `services/repo_knowledge/repo_manager_background_runner.py` (canonical runner)
  - `services/repo_knowledge/grouping/*`
  - `services/repo_knowledge/group_summarization/*`
  - `services/repo_knowledge/prompt_loader.py`
  - `services/repo_knowledge/prompts/*.md`
- Repositories:
  - `infrastructure/repositories/repo_run_repository.py`
  - `infrastructure/repositories/repo_subject_repository.py`
  - `infrastructure/repositories/repo_snapshot_repository.py`
  - `infrastructure/repositories/repo_chunk_repository.py`
  - `infrastructure/repositories/repo_edge_repository.py`
  - `infrastructure/repositories/repo_diagnostic_repository.py`
  - `infrastructure/repositories/repo_file_summary_run_repository.py`
  - `infrastructure/repositories/repo_file_summary_repository.py`
  - `infrastructure/repositories/repo_file_summary_diagnostic_repository.py`
  - `infrastructure/repositories/repo_full_summary_run_repository.py`
  - `infrastructure/repositories/repo_full_summary_repository.py`
  - `infrastructure/repositories/repo_full_summary_diagnostic_repository.py`
  - `infrastructure/repositories/repo_embedding_run_repository.py`
  - `infrastructure/repositories/repo_embedding_repository.py`
  - `infrastructure/repositories/repo_embedding_diagnostic_repository.py`
  - `infrastructure/repositories/repo_group_summary_run_repository.py`
  - `infrastructure/repositories/repo_summary_group_repository.py`
  - `infrastructure/repositories/repo_group_summary_repository.py`
  - `infrastructure/repositories/repo_group_summary_diagnostic_repository.py`
- Models:
  - `infrastructure/models/repo_knowledge.py`

## Data Model
- `repo_runs`
  - Run lifecycle fields, scope/source identifiers, status/error, and counters.
- `repo_subjects`
  - File/class/func/external subjects.
- `repo_file_snapshots`
  - Run-scoped file metadata, ingest status, parse status, and errors.
- `repo_file_chunks`
  - Run-scoped LangChain chunks.
- `repo_edges`
  - Run-scoped dependency edges (imports/exports/defines/calls/inherits/references).
- `repo_parse_diagnostics`
  - Non-fatal parser diagnostics.
- `repo_file_summary_runs`
  - File-summary lifecycle, model settings, and per-run counters.
- `repo_file_summaries`
  - File-level 4-field summaries keyed by file-summary run + subject.
- `repo_file_summary_diagnostics`
  - Non-fatal per-file file-summary diagnostics.
- `repo_full_summary_runs`
  - Repo-level full-summary lifecycle for README generation.
- `repo_full_summaries`
  - Canonical README markdown artifacts keyed by repo-full-summary run.
- `repo_full_summary_diagnostics`
  - Non-fatal diagnostics for repo full-summary generation.
- `repo_embedding_runs`
  - Embedding lifecycle, idempotency fingerprint, and per-run embedding counters.
- `repo_embeddings`
  - Run-scoped summary embedding vectors + embedding source text/hash metadata.
- `repo_embedding_diagnostics`
  - Non-fatal per-subject diagnostics for embedding failures.
- `repo_group_summary_runs`
  - Repo Manager/architecture lifecycle, idempotency fingerprint, counters, and merged repo-level Mermaid artifact.
- `repo_summary_groups`
  - Repo Manager segment definitions (group key/layer/member counts/heuristics).
- `repo_summary_group_members`
  - Segment membership rows with representative rank and assignment reason.
- `repo_group_summaries`
  - LLM-generated per-segment architecture artifacts, including Mermaid diagrams.
- `repo_group_summary_diagnostics`
  - Non-fatal per-segment diagnostics for architecture generation failures.

## Execution Flow
1. API validates scope and input, creates `repo_runs` row (`queued`).
2. In-process background runner dequeues run and marks `in_progress`.
3. Source adapter resolves local path and file iterator.
4. Discovery service applies extension and exclusion filters.
5. Each file is read with binary/size guards.
6. Ingested files are chunked via `RepoChunkingService` (LangChain splitter).
7. Parser registry selects Tree-sitter parser by extension.
8. Parser outputs symbols + edges + diagnostics.
9. Worker upserts subjects, resolves targets (in-repo or external), and persists edges/diagnostics.
10. Run counters and fingerprint are finalized (`completed` or `skipped_duplicate`).
    - when `force_reingest=true`, ingestion finalization is forced to `completed` even if fingerprint matches a previous run.
11. Optional file-summary runs execute asynchronously against completed ingestion runs and persist `repo_file_summaries`.
12. Optional repo-full-summary runs execute asynchronously against completed file-summary runs and persist `repo_full_summaries` (README markdown + trace metadata).
13. Optional pipeline orchestration run (same source run id) monitors stage completion and triggers:
    - file-summary run create/enqueue,
    - repo-full-summary run create/enqueue,
    - embedding run create/enqueue,
    - Repo Manager/architecture run create/enqueue.
    - the Repo Manager stage builds balanced dependency-aware segments from file-summary artifacts.
    - the architecture stage emits Mermaid per segment and one merged repo-level Mermaid artifact.
    - stage queueing is guarded per run so queued stages are enqueued once (prevents duplicate concurrent processing of the same stage run id).
14. LLM failures in segment generation and architecture merge raise structured `TraceableLLMError` objects so diagnostics persist `stage`, `diagnostic_code`, `error_type`, and `raw_text` when available.

## Discovery Robustness
- Discovery now uses `os.walk(..., onerror=...)` and logs inaccessible directories instead of failing the run.
- File-level `is_file()` checks are wrapped with `OSError` handling; inaccessible files are skipped and logged.
- Default excluded directories include `.venv-wsl` to avoid Windows access issues from WSL-managed virtualenv trees.

## Parsing Behavior
- Python:
  - Extracts imports, class/function defines, calls, inheritance, and import-based references.
- TypeScript/JavaScript:
  - Extracts import/export edges, class/function defines, calls, inheritance, and identifier references.
  - Call extraction now accepts identifier/member-expression callees only; complex inline expressions are ignored for call-edge identity to avoid oversized raw expression refs.
- Parser runtime package:
  - Uses `tree_sitter_language_pack` (`get_parser(...)`) rather than deprecated `tree_sitter_languages`.
- Unsupported extensions:
  - File still ingested/chunked; parse status marked `unsupported_language`.

## Summary Extraction Behavior (Phase 2)
- Input coverage:
  - All ingested file snapshots (`ingest_status=ingested`) with chunked text available.
  - Includes unsupported parse languages (for example `.md`) for summarization.
- Prompting/runtime:
  - File summarizer uses LangChain agents (`create_agent(model.bind_tools(tools), tools)`).
  - Runtime invokes native model tool-calling through LangChain tools with bounded recursion/timeout controls.
  - Prompt templates are now:
    - `services/repo_knowledge/prompts/file_summary_system.md`
    - `services/repo_knowledge/prompts/file_summary_user.md`
  - Strict JSON output is still validated against:
    - `file_cluster: list[str]`
    - `overall_summary: str`
    - `important_relationships: list[str]`
    - `group_function: str | None`
- Agent tools (file summarizer only):
  - `return_directory(...)` (filesystem, paginated)
  - `return_file_code(...)` (filesystem, line-paged)
  - `return_reference_graph(...)` (DB graph edges, incoming/outgoing)
- Context enrichment:
  - Base payload still includes file chunks + dependency neighbors from `repo_edges`.
  - Agent tooling can fetch additional file/code/graph context on demand within the same source run scope.
- Long files:
  - Tool-driven paging replaces the old map-reduce file-summary prompt flow.
- Empty files:
  - Deterministic non-LLM fallback summary is stored.

## Repo Full Summary Behavior (Phase 2.5)
- Trigger:
  - Explicit async runs from completed file-summary runs (`POST /repo-knowledge/repo-full-summary-runs`).
  - Pipeline orchestration auto-triggers this stage after file-summary completion.
- Prompting/runtime:
  - LangChain agent runtime (`create_agent(model.bind_tools(tools), tools)`) with prompts:
    - `services/repo_knowledge/prompts/repo_full_summary_system.md`
    - `services/repo_knowledge/prompts/repo_full_summary_user.md`
  - Uses tools:
    - `return_directory(...)`
    - `return_file_code(...)`
    - `return_reference_graph(...)`
    - `return_file_summary(file_name)`
  - Output parsing is strict on `【markdown_start】...【markdown_end】`.
- Persistence:
  - Canonical markdown is stored in `repo_full_summaries.readme_markdown`.
  - Raw agent output + tool trace are stored in `repo_full_summaries.raw_output`.

## Agent Runtime Compatibility Notes
- Native Gemini tool-calling for summary agents now runs on pinned LangChain/LangGraph package versions:
  - `langchain==1.2.12`
  - `langchain-core==1.2.18`
  - `langchain-google-genai==4.2.1`
  - `langgraph==1.1.1`
  - `langgraph-prebuilt==1.0.8`
- Runtime logs these dependency versions once via `services/repo_knowledge/summarization/react_agent_runtime.py` for reproducibility.

## Embedding & Retrieval Behavior (Phase 3)
- Embedding source:
  - File-level `repo_file_summaries` rows from one completed file-summary run (`kind=file_summary`).
- Embedding model:
  - Gemini embedding model via LangChain (`GoogleGenerativeAIEmbeddings`), default `gemini-embedding-001`.
  - Backward-compatibility alias fallback is enabled for model naming differences across Gemini API/SDK variants.
  - Embedding calls set `output_dimensionality` to `REPO_EMBED_VECTOR_DIM` so vector length matches pgvector schema.
- Embedding execution:
  - Asynchronous embedding runs with per-batch commits and per-subject fallback/diagnostics.
- Vector storage:
  - Stored in `repo_embeddings.embedding` (pgvector when available) with ivfflat cosine index.
- Context-pack retrieval:
  - Query embedding -> top semantic candidates -> summary hydration -> Gemini business-focused rerank -> file neighbor expansion -> symbol hint expansion.
- Rerank fallback:
  - If Gemini rerank fails, context-pack degrades to vector-only ordering and marks `rerank_applied=false`.

## Group Summary Behavior (Phase 3.5)
- Trigger:
  - Explicit async runs from completed file-summary runs (`POST /repo-knowledge/group-summary-runs`).
- Group construction:
  - `HybridPathDependencyGrouper` builds deterministic groups from:
    - file summaries (`repo_file_summaries`),
    - file-to-file edges (`repo_edges`, non-external).
  - Stage A: path seeds (`REPO_GROUP_PATH_DEPTH`).
  - Stage B: dependency-affinity merges (`REPO_GROUP_DEP_MERGE_MIN_AFFINITY`, `REPO_GROUP_MAX_MEMBER_FILES`).
  - Stage C: layer/infrastructure heuristics + representative file ranking.
- Group summarization:
  - Gemini 2.5 Flash hard-set internally (not API-exposed).
  - Strict JSON schema:
    - `name`, `overall_summary`, `business_purpose`,
    - `responsibilities`, `tags`, `representative_subject_ids`,
    - `is_infrastructure`, `confidence`.
  - Per-group failure isolation with diagnostics; run continues.
- Persistence:
  - Deterministic groups/members are persisted before LLM summarization.
  - Summaries are upserted per group in `repo_group_summaries`.

## Tenancy and Security
- All run/file/edge reads are scoped by `tenant_id + user_id`.
- Local path ingestion is constrained to `REPO_INGEST_ALLOWED_ROOTS`.

## Configuration
Added settings:
- `REPO_INGEST_ALLOWED_ROOTS`
- `REPO_INGEST_ALLOWED_EXTENSIONS`
- `REPO_INGEST_EXCLUDED_DIRS`
- `REPO_INGEST_MAX_FILE_BYTES`
- `REPO_INGEST_CHUNK_SIZE`
- `REPO_INGEST_CHUNK_OVERLAP`
- `REPO_INGEST_MAX_CONCURRENT_RUNS`
- `REPO_PARSE_MAX_FILE_BYTES`
- `REPO_PARSE_LANGUAGES`
- `REPO_SUMMARY_MAX_CONCURRENT_RUNS`
- `REPO_SUMMARY_PROMPT_VERSION`
- `REPO_SUMMARY_MODEL_PROVIDER`
- `REPO_SUMMARY_MODEL_NAME`
- `REPO_SUMMARY_TEMPERATURE`
- `REPO_SUMMARY_MAX_INPUT_CHARS`
- `REPO_SUMMARY_MAP_CHUNK_CHARS`
- `REPO_SUMMARY_MAX_OUTPUT_TOKENS`
- `REPO_SUMMARY_RETRY_COUNT`
- `REPO_SUMMARY_TIMEOUT_SECONDS`
- `REPO_SUMMARY_NEIGHBOR_LIMIT_EACH_DIRECTION`
- `REPO_EMBED_MAX_CONCURRENT_RUNS`
- `REPO_EMBED_MODEL_PROVIDER`
- `REPO_EMBED_MODEL_NAME`
- `REPO_EMBED_VECTOR_DIM`
- `REPO_EMBED_BATCH_SIZE`
- `REPO_EMBED_TIMEOUT_SECONDS`
- `REPO_CONTEXT_TOP_K`
- `REPO_CONTEXT_CANDIDATE_K`
- `REPO_CONTEXT_NEIGHBOR_LIMIT_EACH_DIRECTION`
- `REPO_CONTEXT_SYMBOL_HINT_LIMIT`
- `REPO_CONTEXT_RERANK_MODEL_NAME`
- `REPO_CONTEXT_RERANK_TIMEOUT_SECONDS`
- `REPO_CONTEXT_RERANK_MAX_CANDIDATES`
- `REPO_GROUP_SUMMARY_MAX_CONCURRENT_RUNS`
- `REPO_GROUP_SUMMARY_PROMPT_VERSION`
- `REPO_GROUP_SUMMARY_TIMEOUT_SECONDS`
- `REPO_GROUP_SUMMARY_RETRY_COUNT`
- `REPO_GROUP_SUMMARY_MAX_INPUT_CHARS`
- `REPO_FULL_SUMMARY_MAX_CONCURRENT_RUNS`
- `REPO_FULL_SUMMARY_PROMPT_VERSION`
- `REPO_FULL_SUMMARY_TIMEOUT_SECONDS`
- `REPO_FULL_SUMMARY_RETRY_COUNT`
- `REPO_FULL_SUMMARY_MAX_INPUT_CHARS`
- `REPO_FULL_SUMMARY_MAX_ITERATIONS`
- `REPO_GROUP_PATH_DEPTH`
- `REPO_GROUP_DEP_MERGE_MIN_AFFINITY`
- `REPO_GROUP_MAX_MEMBER_FILES`
- `REPO_GROUP_REPRESENTATIVE_COUNT`
- `REPO_PIPELINE_MAX_CONCURRENT_RUNS`
- `REPO_PIPELINE_POLL_SECONDS`

## Cross-Feature Impact
- Additive feature; existing document/thread/Graphiti routes are unchanged.
- `main.py` lifespan now starts/stops ingestion, file-summary, repo-full-summary, embedding, group-summary, and pipeline workers.
- `main.py` lifespan now also starts/stops the repo embedding worker.
- `main.py` lifespan now also starts/stops the repo group-summary worker.
- `Base.metadata.create_all` now creates additional repo-knowledge tables.
- Summary model provider selection is explicit per stage and uses LangChain model interfaces.
- DB bootstrap now attempts `CREATE EXTENSION IF NOT EXISTS vector` for pgvector support.

## Observability
- `main.py` has global FastAPI exception handlers that log:
  - all HTTP exceptions (including Starlette-generated route/HTTP errors),
  - request validation errors,
  - unhandled 500 exceptions with stack traces.
- Request validation error payloads are now JSON-safe serialized before response emission so `ctx.error` exception objects (from model validators) cannot trigger response-serialization 500s.
- Repo-knowledge router/service/runner/parser/discovery/chunking modules emit step-level logs to support end-to-end ingestion debugging.
- File-summary and repo-full-summary router/service/runner/summarizer modules emit step-level logs for run lifecycle, per-file/repo failures, and diagnostics.

## Edge Persistence Reliability
- Parse edges are deduplicated in-memory before persistence using the same identity tuple as the DB unique constraint:
  - `(run_id, from_subject_id, to_subject_id, edge_type, line, column)`.
- `RepoEdgeRepository.create_many(...)` now uses PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` against the edge identity constraint to avoid run-fatal duplicate edge insert failures.
- Worker exception path logs and cleanup use stable scalar `run_id` values, avoiding ORM attribute access after rollback when the session is in failed state.
- External target fallback now prefers short symbolic refs for `calls`/`references`/`inherits` before raw expression text.
- External refs are canonicalized and length-capped; oversized refs are replaced with deterministic `ext_sha256:<digest>` identities, with warning diagnostics including a short preview.
- External subject insert failures are isolated at edge level: the edge is skipped, a warning diagnostic is recorded, and ingestion continues instead of failing the entire run.

## Duplicate-Tolerant Lookup Behavior
- Ingestion-critical repository lookups are now defensive against historical duplicate rows and no longer rely on strict single-row fetch semantics in those paths.
- Updated repositories:
  - `RepoSubjectRepository`: `get_by_id`, `find_file_by_path`, `find_symbol_by_qualname`, `find_symbol_by_name`
  - `RepoSnapshotRepository`: `upsert` pre-read
  - `RepoRunRepository`: `get`, `get_scoped`, `find_completed_by_fingerprint`
- Behavior:
  - queries use deterministic ordering and fetch up to 2 rows;
  - if duplicates are observed, a warning is logged;
  - the oldest deterministic row is used so ingestion can continue.

## LLM Provider Abstraction
- File-summary/repo-full-summary/group-summary runtimes use LangChain chat model interfaces with provider-specific adapters:
  - OpenAI (`langchain-openai`)
  - Gemini (`langchain-google-genai`)
  - Anthropic (`langchain-anthropic`)
- Provider package/key/configuration errors fail summary runs explicitly with actionable error messages.
- Default summary provider is configured as Gemini (`REPO_SUMMARY_MODEL_PROVIDER=gemini`) unless overridden.
- Current runtime policy hard-locks:
  - file-summary runs to `gemini` + `gemini-3-flash-preview`,
  - repo-full-summary runs to `gemini` + `gemini-3-flash-preview`,
  - group-summary runs to `gemini` + `gemini-2.5-flash`.
  - For file-summary/repo-full-summary: tool usage is currently routed through text-protocol orchestration because Gemini function-calling with LangChain does not yet preserve required thought signatures across tool turns.
  - Provider/model are internal-only and not exposed via summary APIs.
- Embedding and rerank model/provider selection remain internal-only and are not exposed via embedding/context-pack APIs.
- Prompt source for repo-knowledge LLM operations is file-backed (no inline fallback constants):
  - file summary prompts: `services/repo_knowledge/prompts/file_summary_*.md`
  - repo full summary prompts: `services/repo_knowledge/prompts/repo_full_summary_*.md`
  - group summary prompts: `services/repo_knowledge/prompts/group_summary_*.md`
  - business rerank prompts: `services/repo_knowledge/prompts/rerank_business_logic_*.md`
  - loader utility: `services/repo_knowledge/prompt_loader.py` (`load_prompt`, `render_prompt`)

## MCP Tooling (Read Surface)
- Added read-focused MCP server entrypoint:
  - `scripts/repo_knowledge_mcp_server.py`
  - Script now bootstraps repo root into `sys.path` so `mcp run scripts/...` resolves project imports (`config`, `infrastructure`, `services`) reliably.
- Added MCP service layer:
  - `services/repo_knowledge/mcp_tools_service.py`
- Implemented MCP tools for table-level inspection and summary reading:
  - `repo_run_overview`
  - `repo_list_files`
  - `repo_list_edges`
  - `repo_list_summaries`
  - `repo_read_summary_file`
  - `repo_list_embedding_items`
  - `repo_list_group_summaries`
  - `repo_read_group_summary`
  - `repo_structure`
- `repo_list_summaries` item payload is minimized for agent consumption:
  - omits `source_run_id` and `file_summary_run_id` at the per-item level.
  - run-level identifiers remain in top-level response fields.
- Scope behavior:
  - Tools enforce tenant/user scoping via `tenant_id` + `user_id`.
  - When placeholder scope is enabled, missing scope args fall back to configured defaults.
- Context-pack remains available in HTTP APIs, but MCP tools now provide the primary read path for summarized repo artifacts.
