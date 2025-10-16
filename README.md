# Context Retrieval Backend

A multi-tenant Retrieval-Augmented Generation (RAG) service built with FastAPI, async SQLAlchemy, LangChain, and SentenceTransformers. It ingests documents, creates chunk-level and document/project summaries, stores embeddings in pgvector or Milvus, and answers natural-language questions with sourced responses.

---

## At a Glance

- **API surface:** ingest, manage, and delete documents; submit queries; retrieve responses and supporting sources.
- **Multi-tenancy:** every request runs with a `ContextScope` (tenant + project list + user) enforced by PostgreSQL row-level security.
- **Vector stores:** pluggable adapter for pgvector or Milvus; same ingestion/search code path works for both.
- **Summaries:** document-level summaries are generated and stored in PostgreSQL and Milvus (when configured); project summaries aggregate document summaries to provide high-level context.
- **Version control:** optional git integration mirrors uploaded documents to disk and commits them.
- **Reset utilities:** `scripts/reset_state.py` drops/recreates tables, reconfigures RLS, clears summaries, purges Milvus collections, and deletes on-disk document artifacts.

---

## Prerequisites

- Python **3.11+**
- PostgreSQL 14+ (with `pgvector` extension available)
- Install milvus using the docker compose:
     https://milvus.io/docs/install_standalone-docker-compose.md
- Valid Anthropic API key for LLM-driven summarization and query flows (`claude-3-5-haiku-latest`)
- Git installed when using the document versioning feature

> **Note:** SentenceTransformers downloads the `BAAI/llm-embedder` model at runtime; ensure the host can reach Hugging Face or pre-cache the model in the environment.

---

## Quick Start

```powershell
# Clone and enter the backend directory
git clone <repo-url>
cd context-retrieval-backend

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your environment configuration
copy .env.example .env  # (create manually if the example is not provided)
```

### Required environment variables (`.env`)

| Key | Description |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy URL to PostgreSQL (e.g. `postgresql+asyncpg://user:pass@localhost:5432/context`) |
| `ANTHROPIC_API_KEY` | API key for Anthropic Claude (used for chunk contextualization, document/project summaries, query answering) |
| `OPENAI_API_KEY` | Optional – required if you switch `LLM_PROVIDER` to `openai` |
| `LLM_PROVIDER` | `anthropic` (default) or `openai` |
| `VECTOR_STORE_MODE` | `pgvector` (default) or `milvus` |
| `EMBEDDING_VECTOR_DIM` | Dimension of the embeddings (default `768`, matches `BAAI/llm-embedder`) |
| `MILVUS_HOST` / `MILVUS_PORT` | Milvus connection info when using the Milvus backend |
| `MILVUS_COLLECTION_NAME` | Main collection for chunk vectors (default `document_chunks`) |
| `MILVUS_DOCUMENT_SUMMARY_COLLECTION_NAME` | Collection for document summary vectors (defaults to `document_summary_vectors`) |
| `MILVUS_PROJECT_SUMMARY_COLLECTION_NAME` | Collection for project summary vectors (defaults to `project_summary_vectors`) |
| `MILVUS_VECTOR_DIM` | Milvus collection vector dimension (defaults to `EMBEDDING_VECTOR_DIM`) |
| `MILVUS_CONSISTENCY_LEVEL` | Read consistency (defaults to `Bounded`) |
| `GIT_REPO_PATH` | Optional absolute path to a git repo for storing uploaded documents |

### Bootstrap the database and stores

```powershell
.venv\Scripts\activate
python scripts\reset_state.py
```

`reset_state.py` performs the following:
1. Drops and recreates all PostgreSQL tables (documents, chunks, embeddings, summaries, knowledge graph, etc.).
2. Reapplies row-level security policies.
3. Seeds the default tenant, project, and admin role.
4. Drops Milvus collections (`document_chunks`, document summary, project summary) if using Milvus.
5. Clears the `{GIT_REPO_PATH}/documents` folder so git mirrors remain in sync.

### Run the API

```powershell
.venv\Scripts\activate
python main.py
# or uvicorn main:app --reload
```

`main.py` configures the application lifecycle: enabling `pgvector`, creating tables, applying policies, seeding defaults, and wiring FastAPI routes.

---

## Architecture Overview

### Request Context & Multi-tenancy
- `routers.dependencies.get_request_context_bundle` resolves tenant/project scope for the authenticated user.
- `ContextScope` is injected into repositories/services and also registered with PostgreSQL via `set_app_context`.
- All repositories filter by `tenant_id` and `project_id` (RLS enforces the same constraints at the DB level).

### Document Ingestion
`DocumentProcessingService.upload_and_process_document` orchestrates ingestion:
1. **Persist metadata** via `DocumentRepository`.
2. **Chunking:** `Chunker` uses Markdown header-aware splitting plus recursive character splitting.
3. **Contextualization:** each chunk is enriched with additional context using an Anthropic prompt (`Embedder.contextualize_chunk_content`).
4. **Embeddings:** SentenceTransformer `BAAI/llm-embedder` encodes contextualized chunks; vectors are persisted via the active `VectorStoreGateway`.
5. **Summaries:** `DocumentSummaryService` generates an LLM-based summary for the full document; `ProjectSummaryService` consolidates document summaries into a project-level overview.
6. **Knowledge Graph (optional):** `KnowledgeGraphService` updates graph entities and relationships.
7. **Version-control:** when `GIT_REPO_PATH` is configured, the document content is written to disk and committed via `GitService`.

### Query Answering
`QueryService.process_query` coordinates the question answering flow:
1. Persist the query and create a placeholder response row.
2. `ClauseFormer` breaks the user’s query into sub-questions using `SubquestionDecomposer` (LLM-generated with JSON parsing fallbacks).
3. For each sub-question:
   - Search the vector store via the LangChain tool set (`search_chunks`).
   - Pass retrieved context, optional conversation history, and instructions into the LLM to produce a `ClauseFormat` (statement + referenced chunk IDs).
   - Resolve chunk IDs to full `Source` objects (content + metadata).
4. Combine the statements into a final response, persist response text/status, and save source attributions.

### Summaries
- **Document Summaries:** `DocumentSummaryService` stores text + metadata in the `document_summaries` table and (when Milvus is active) pushes summary vectors into the summary collection.
- **Project Summaries:** `ProjectSummaryService` aggregates document summaries per project to keep a high-level view current. Updates occur after document ingestion; the service handles both initial creation and incremental updates.

---

## Key Components & Code Map

| Area | Location | Notes |
| --- | --- | --- |
| HTTP API | `routers/` | Documents, queries, dependencies; `main.py` mounts routers. |
| Services | `services/` | Business workflows for documents, queries, summaries, knowledge, search. |
| Repositories | `infrastructure/database/repositories/` | Async SQLAlchemy repositories scoped by `ContextScope`. |
| Models | `infrastructure/database/models/` | ORM definitions (`documents`, `chunks`, summaries, knowledge graph, tenancy, etc.). |
| Vector Store | `infrastructure/vector_store/` | `PgVectorStore`, `MilvusVectorStore`, and factory/wrappers. |
| AI Helpers | `infrastructure/ai/` | Chunker, embedder, user intent decomposition, Milvus tooling, prompt loaders. |
| Config | `config/settings.py` | Central place for environment configuration. |
| Reset & Smoke Tests | `scripts/reset_state.py`, `scripts/milvus_smoke_test.py`, `tests/` | Admin utilities and automated checks. |

---

## API Endpoints (current)

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/upload` | Upload `.txt`/`.md` document, chunk, embed, summarize, and index it. |
| `GET` | `/api/documents` | List documents for the current tenant/project scope. |
| `GET` | `/api/documents/{doc_id}` | Retrieve full document content and metadata. |
| `PUT` | `/api/documents/{doc_id}` | Update document content and regenerate chunks/embeddings/summaries. |
| `DELETE` | `/api/documents/{doc_id}` | Delete document, chunks, embeddings, summaries. |
| `PUT` | `/api/documents/{doc_id}/chunks/{chunk_id}` | Edit individual chunk content. |
| `POST` | `/api/query` | Submit a question and receive a sourced answer. |
| `GET` | `/health` | Health probe. |

> Query and document routes expect valid tenant/project context (usually set via auth middleware or dependencies).

---

## Running Tests & Smoke Checks

```powershell
.venv\Scripts\activate
python -m pytest
```

Environment-gated tests:
- `RUN_E2E_SMOKE_TESTS=1` — run HTTP ingestion/query smoke test (requires API running separately).
- `RUN_MILVUS_SMOKE_TESTS=1` — include Milvus adapter smoke tests (requires Milvus).

Standalone script:

```powershell
.venv\Scripts\activate
python scripts\milvus_smoke_test.py  # when using Milvus
```

---

## Operational Notes

- **Resets:** Use `python scripts/reset_state.py` whenever you need a clean slate (drops DB + Milvus + document directory).
- **Embedding dimension:** Ensure `EMBEDDING_VECTOR_DIM` and `MILVUS_VECTOR_DIM` align with the embedding model output.
- **LLM costs:** Document and project summarization, chunk contextualization, and query responses all consume Anthropic tokens. Adjust prompts/thresholds as needed for cost control.
- **Milvus collections:** Collection names default to `document_chunks`, `document_summary_vectors`, and `project_summary_vectors`; override via environment variables if you run multiple instances against the same Milvus cluster.
- **Git mirroring:** Set `GIT_REPO_PATH` to a repository containing a `documents/` folder; the service will stage and commit changes with a generic author unless overridden by `GIT_AUTHOR_NAME/EMAIL`.

---

## Extending the System

- **New document formats:** Enhance `Chunker` or add preprocessing steps before `DocumentProcessingService.process_document`.
- **Alternative LLM providers:** Update `config/settings.py` and the service constructors to inject different `BaseChatModel` instances.
- **Custom vector stores:** Implement `VectorStoreGateway` and register it in `infrastructure/vector_store/factory.py`.
- **Scheduling summary refreshes:** `ProjectSummaryService` exposes `update_summary()` for manual or scheduled triggers.

---

## Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| `ProgrammingError: relation ... already exists` | Metadata mismatch between ORM and DB (e.g., manual schema tweaks) | Run `python scripts/reset_state.py` or Alembic migrations as needed. |
| `tuple object has no attribute content` on document upload | LLM response returned as tuple/list | Ensure the latest code with `_coerce_to_text` helpers is deployed. |
| `Input to ChatPromptTemplate is missing variables {'message_history'}` | Pipeline dropped the history variable | Confirm `ClauseFormer` is passing `message_history` through (fixed in latest code). |
| Milvus connection errors | Incorrect host/port or auth | Verify env vars, run `scripts/milvus_smoke_test.py`, check Milvus server status. |
| Missing git commits | `GIT_REPO_PATH` not set or repo path invalid | Configure env var to a valid repo; check logs for pygit2 errors. |

