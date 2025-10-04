# Copilot Instructions

## Architecture & Flow
- `main.py` boots FastAPI with a lifespan hook that enables the `vector` extension and creates tables if missing; all routers live under `/api`.
- Requests receive an `AsyncSession` via `Depends(get_db)` in `infrastructure/database/database.py`; services never call `commit()` (FastAPI commits on success, rolls back on exception).
- Document ingestion runs through `DocumentProcessingService`: store metadata, chunk via `Chunker` (LangChain splitters), contextualize with `Embedder.llm_provider`, then persist chunk embeddings (`pgvector`).
- Queries go through `QueryService`: create the `queries` row, generate an embedding, run semantic search via `SearchRepository.semantic_vector_search`, update a placeholder `responses` row, then attach `sources`.
- Repositories in `infrastructure/database/repositories/` wrap SQLAlchemy models; most write paths call `flush()` only. Deletion helpers (`ChunkRepository.delete_*`) do call `commit()`, so avoid mixing them with additional manual transaction control.

## Key Conventions
- Long-running or synchronous work (SentenceTransformer encode, LangChain splitting, LLM calls) is dispatched with `asyncio.get_event_loop().run_in_executor` to keep the event loop responsive.
- Prompts live in `prompts/*.md` and are loaded via `infrastructure/utils/prompt_loader.py`; reuse `load_prompt` instead of hard-coding strings.
- Embeddings use the `BAAI/llm-embedder` SentenceTransformer by default; plan for model download on first run.
- LLM provider is selected through `config/settings.py` (`LLM_PROVIDER` env var). The factory in `infrastructure/external/llm_provider.py` returns an Anthropic or OpenAI client.
- Database schema is split between `documents.py` (documents, chunks, embeddings) and `queries.py` (queries, responses, sources); relationships enforce one response per query and one embedding per chunk.

## Environment & Secrets
- `.env` must define `DATABASE_URL` (asyncpg DSN) and the relevant API keys (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`).
- Postgres must have `pgvector` available; the app issues `CREATE EXTENSION IF NOT EXISTS vector` during startup.

## Run & Test
```powershell
# Activate the virtualenv before running anything
.venv\Scripts\activate

# Launch the API with auto-reload (listens on :8000)
python main.py

# Happy-path smoke test for upload flow
python test_sync_upload.py

# Full suite (pytest-based) – optional but available
# Always run from the tests directory so discovery works as expected
cd tests
pytest
```

## Practical Tips
- When working in planning or architecture mode, read the `.planning/` markdown files first. Update them with new assumptions, decisions, or todo items before touching source code so the shared knowledge stays current. Planning sessions should update `knowledge-base-plan.md` and `roadmap.md`, and when new milestones emerge, add dedicated `.planning/*.md` milestone files outlining implementation steps. When planning and coding, always try to follow the current file structure and conventions.
- Drafting workflow (agent-first source of truth):
	1. Before implementation begins on a milestone, create or refresh `.planning/draft-<milestone>.md`.
	2. Drafts must be complete enough that a coding agent can implement without guessing—include schema diffs, API signatures, migration snippets, config/feature flags, rollout steps, test plans, observability, and rollback notes.
	3. Keep drafts synchronized with `knowledge-base-plan.md` (link active drafts) and update them as decisions change. Once work lands, summarize outcomes back into the milestone file.
	4. If a draft reveals open questions, capture them explicitly with owners; do not leave assumptions implicit.
- Implementation workflow & milestone evaluation:
	- Treat each milestone draft as the contract. Translate draft tasks directly into issues/PR checklists and do not improvise new scope without updating the draft first.
	- Add or update automated tests under `tests/` for every behavior change. Include regression tests replicating the original bug or scenario.
	- Run targeted test modules after localized edits; before marking a milestone complete, execute the full pytest suite to guard against unintended regressions.
	- When feasible, add smoke or integration tests that span the full milestone surface (e.g., API flow + DB assertions).
	- Document verification results (tests run, commands executed, outcomes) in the PR or summary so downstream agents know the state.
- When working in coding mode, read the relevant `.planning/` markdown files to understand the high-level design and intended functionality before implementing or modifying code.
- After landing a change or closing an issue, update `roadmap.md` (and any affected milestone files) to reflect the new status before marking the task complete.
- When extending services, you must add small repository helpers and will never issue raw SQL in the service layer.
- Reuse existing Pydantic schemas in `schemas/` for new responses to keep typing consistent.
- If you introduce new LLM prompts, drop them into `prompts/` and reference by stem name to benefit from prompt caching.
- For additional vector search behavior (filters, limits), extend `SearchRepository.semantic_vector_search`—it is the single choke point translating embeddings to SQL.
- All code will follow single responsibility principle and be organized into layers: Models, Repositories, Infrastructure, Services, Routers.
