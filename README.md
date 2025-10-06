# Context Retrieval Backend

A FastAPI-based retrieval augmented generation backend that ingests documents, builds semantic indexes, and answers queries across multi-tenant projects.

## Current Capabilities
- **Application lifecycle:** `main.py` enables the `pgvector` extension, auto-creates tables, configures row-level security for multi-tenant access, and seeds a default tenant/project during startup.
- **Scope-aware request handling:** every request resolves a `ContextScope` (tenant, project list, user) and registers it with PostgreSQL through `set_app_context` to enforce data isolation.
- **Document ingestion API:** `/api/upload` accepts `.txt` and `.md` uploads, persists the raw document, splits it with markdown-aware chunking, contextualizes each chunk with an LLM prompt, embeds the content, and upserts vectors into the configured store.
- **Document management:** `/api/documents` supports listing, fetching, and deleting stored documents while keeping vector indexes and on-disk copies in sync.
- **Query answering:** `/api/query` records each query, embeds the prompt, performs top-k semantic search per tenant/project, calls the configured LLM to synthesize an answer, and stores response plus source snippets.
- **Vector store abstraction:** adapters for both PostgreSQL `pgvector` and Milvus are wired through a common gateway so the same code path handles ingestion and search for either backend.
- **Embedding & LLM integrations:** SentenceTransformer `BAAI/llm-embedder` powers embeddings; LLM provider selection is centralized via `config.settings` and supports OpenAI or Anthropic clients.
- **Version-controlled artifacts:** when `GIT_REPO_PATH` is set, uploaded or deleted documents are mirrored to disk and committed through a pygit2-backed `GitService`.

## API Surface (implemented)
| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/api/upload` | Upload a `.txt` or `.md` document, chunk, embed, and index it. |
| `GET` | `/api/documents` | List stored documents for the active tenant/project scope. |
| `GET` | `/api/documents/{doc_id}` | Retrieve document metadata and UTF-8 content. |
| `DELETE` | `/api/documents/{doc_id}` | Remove a document, associated chunks, and vectors. |
| `POST` | `/api/query` | Embed a user query, run semantic search, and return synthesized answer + sources. |
| `GET` | `/health` | Basic service health probe. |

## Processing Pipelines
### Document Flow
1. Persist document metadata/content via `DocumentRepository` without immediate commit (FastAPI handles transaction lifecycle).
2. Split text with `Chunker` (Markdown-aware + recursive character splitter) running in an executor to stay non-blocking.
3. Contextualize each chunk with an LLM prompt (`prompts/contextualize_chunk.md`) and embed via SentenceTransformer.
4. Persist chunk rows, upsert vector embeddings through `VectorStoreGateway`, and optionally stage file artifacts + git commit.

### Query Flow
1. Create a query row and generate an embedding for the request text.
2. Execute semantic search constrained to tenant/project scope using the active vector backend.
3. Record a placeholder response row, call the configured LLM with top search contexts, then update the response text and status.
4. Persist source links for each retrieved chunk to drive attribution in downstream clients.

## Storage & Infrastructure
- **Database:** Async SQLAlchemy models with repositories for documents, chunks, queries, responses, and sources; helper deletes ensure vectors are cleaned alongside relational rows.
- **Vector backends:** `PgVectorStore` performs similarity queries via SQL; `MilvusVectorStore` integrates with Milvus SDK, with health and smoke tests under `scripts/` and `tests/`.
- **Context propagation:** `routers.dependencies.get_request_context_bundle` resolves tenant/project membership from `UserProjectRole` and ensures a single-tenant constraint before serving requests.

## Test & Verification Coverage
- `tests/test_sync_upload.py` validates the synchronous upload pathway, database writes, and vector index interactions.
- `tests/test_end_to_end_smoke.py` drives the HTTP stack (FastAPI + background processing) for upload and query flows when the API is running.
- `tests/test_vector_store.py` and `tests/test_milvus_vector_store.py` cover pgvector and Milvus adapters respectively.
- `tests/test_milvus_smoke.py` exercises Milvus connectivity with optional environment gating.
- `tests/test_multi_tenant_repositories.py` verifies tenant/project scoping across repositories.
- `tests/test_git_versioning.py` ensures git commits trigger correctly when repository settings are supplied.

## Runbook
### Start the API
```powershell
.venv\Scripts\activate
python main.py
```

### Milvus Smoke Test
```powershell
# Requires VECTOR_STORE_MODE=milvus with Milvus/PostgreSQL reachable
.venv\Scripts\activate
python scripts\milvus_smoke_test.py
```

### HTTP End-to-End Smoke Test
```powershell
# Terminal 1 – start the API
.venv\Scripts\activate
python main.py

# Terminal 2 – run the smoke test suite
$env:RUN_E2E_SMOKE_TESTS="1"
.venv\Scripts\activate
python -m pytest tests/test_end_to_end_smoke.py
```

The HTTP smoke test self-skips if the API is unreachable. Set `RUN_MILVUS_SMOKE_TESTS=1` to include Milvus checks inside the pytest run. Ensure `MILVUS_VECTOR_DIM` matches the embedding model output (`768` by default).
