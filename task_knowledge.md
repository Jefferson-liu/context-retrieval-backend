# Task Knowledge: Context-Retrieval Backend API Completion

## Overview
- **Purpose**: Backend for context-retrieval POC. Handles document upload, chunking, embedding, storage, and search/query using FastAPI, SQLAlchemy, pgvector, AI models (SentenceTransformer, Anthropic), and external APIs.
- **Tech Stack**: FastAPI, PostgreSQL (pgvector), SQLAlchemy, SentenceTransformer, scikit-learn, LangChain.
- **Architecture**: Layered (infrastructure: utilities; services: logic; repositories: data access).
- **Workflows**: Upload → Chunk → Contextualize → Embed → Store; Query → Search → Return results.

## File Structure
```
root/
├── infrastructure/
│   ├── database/
│   │   ├── database.py (engine, session, base)
│   │   ├── models/
│   │   │   ├── documents.py (UploadedDocument, Chunk, Embedding)
│   │   │   └── queries.py (Query, Response, Source)
│   │   └── repositories/
│   │       ├── document_repository.py
│   │       ├── search_repository.py
│   │       └── __init__.py
│   ├── ai/
│   │   ├── chunking.py (Chunker)
│   │   └── embedding.py (Embedder)
│   ├── utils/
│   │   └── prompt_loader.py
│   └── external/
│       └── anthropic_interface.py
├── services/
│   ├── document/
│   │   └── processing.py (DocumentProcessingService)
│   └── ai/
│       └── embedding_service.py (EmbeddingService)
├── routers/ (incomplete: needs upload.py, search.py, __init__.py)
├── main.py (empty: needs FastAPI setup)
├── requirements.txt
└── .env
```

## Key Components

### Infrastructure Layer
#### Database
- **database.py**:
  - `Base`: Declarative base.
  - `engine`: SQLAlchemy engine.
  - `SessionLocal`: Session factory.
  - `get_db()`: FastAPI dependency (yields session).
  - `create_tables()`: Optional table creation.

- **Models**:
  - **documents.py**:
    - `UploadedDocument`: Fields: id, doc_name, content, doc_size, upload_date, doc_type.
    - `Chunk`: Fields: id, doc_id, chunk_order, content, raw_content.
    - `Embedding`: Fields: id, chunk_id, embedding (vector), tfidf_embedding (vector), content, context, raw_content, chunk_order.
  - **queries.py**:
    - `Query`: Fields: id, query_text, created_date, status. Relationships: response (1:1).
    - `Response`: Fields: id, query_id, response_text, status. Relationships: query (M:1), sources (1:M).
    - `Source`: Fields: id, response_id, chunk_id, doc_id. Relationships: response (M:1), chunk (M:1 via composite join).

- **Repositories**:
  - **document_repository.py** (`DocumentRepository`):
    | Method | Signature | Notes |
    |--------|-----------|-------|
    | `__init__` | `(db)` | Injects session. |
    | `create_document` | `(doc_name, content, doc_size, doc_type)` | Returns document. |
    | `edit_document` | `(doc_id, **kwargs)` | Updates document. |
    | `get_all_documents` | `()` | Returns list. |
    | `get_document_by_id` | `(document_id)` | Returns single. |

  - **search_repository.py** (`SearchRepository`):
    | Method | Signature | Notes |
    |--------|-----------|-------|
    | `__init__` | `(db)` | Injects session. |
    | `semantic_vector_search` | `(query_embedding, top_k)` | Returns tuples. |

#### AI Utilities
- **chunking.py** (`Chunker`):
  | Method | Signature | Notes |
  |--------|-----------|-------|
  | `__init__` | `()` | Initializes splitter. |
  | `chunk_text` | `(content, filename)` | Async. |
  | `chunk_general` | `(content, filename)` | Async. |

- **embedding.py** (`Embedder`):
  | Method | Signature | Notes |
  |--------|-----------|-------|
  | `__init__` | `()` | Loads model. |
  | `generate_embedding` | `(text)` | Async, returns list[float]. |

#### Other Infrastructure
- **utils/prompt_loader.py**: `load_prompt(name)` - Loads prompt strings.
- **external/anthropic_interface.py**: `get_anthropic_response(prompt)` - Async API call.

### Services Layer
- **document/processing.py** (`DocumentProcessingService`):
  | Method | Signature | Notes |
  |--------|-----------|-------|
  | `__init__` | `(db)` | Injects session. |
  | `upload_and_process_document` | `(content, doc_name, doc_type)` | Async, full workflow. |
  | `process_document` | `(document_id, content)` | Async, chunk/embed. |
  | `delete_document` | `(document_id)` | Returns bool. |
  | `get_document` | `(document_id)` | Returns document. |
  | `list_documents` | `()` | Returns list. |
  | `update_document_content_from_chunks` | `(doc_id)` | Reassembles content. |

- **ai/embedding_service.py** (`EmbeddingService`):
  | Method | Signature | Notes |
  |--------|-----------|-------|
  | `__init__` | `(db)` | Injects session. |
  | `chunk_file_content` | `(content, filename)` | Async. |
  | `contextualize_chunk_content` | `(chunk_content, full_content)` | Async. |
  | `reconstruct_file_content` | `(file_id)` | Returns str. |
  | `embed_file` | `(file_id, content, filename)` | Async, full embed. |
  | `_update_all_tfidf_embeddings` | `(vectorizer)` | Private, sync. |

### Routers Layer (Incomplete)
- `routers/__init__.py`: Empty package.
- `routers/upload.py`: Missing - Needs endpoints for upload, list, get, delete documents.
- `routers/search.py`: Missing - Needs endpoints for semantic/TF-IDF search, query processing.

### Other Files
- **main.py**: Empty - Needs FastAPI app, router inclusion, CORS, DB startup.
- **requirements.txt**: Lists dependencies (fastapi, sqlalchemy, etc.).
- **.env**: Environment vars (e.g., DATABASE_URL).

## Dependencies and Imports
- **Core**: fastapi, sqlalchemy, pgvector, sentence-transformers, sklearn, langchain-text-splitters.
- **Async**: Used for I/O (API calls, chunking).
- **DB**: PostgreSQL with pgvector.
- **Environment**: DATABASE_URL from .env.
- **Imports**: Relative paths (e.g., `from infrastructure.database.database import Base`).

## Known Issues/Gaps
- Routers: `upload.py`, `search.py` missing; no endpoints exist.
- Services: `QueryService` referenced but not implemented.
- Models: Relationships defined but untested.
- Error Handling: Minimal; add try/except.
- Testing: No unit tests.

## Tasks to Complete
1. Create `routers/upload.py`: POST /upload, GET /documents, GET /documents/{id}, DELETE /documents/{id} (use DocumentProcessingService).
2. Create `routers/search.py`: POST /search/semantic, POST /search, POST /query (use QueryService).
3. Update `routers/__init__.py`: Package file.
4. Update `main.py`: FastAPI app, include routers, CORS, DB startup.
5. Implement `services/queries/query_service.py` (QueryService).
6. Test integration; create scripts to validate functionality. Delete test scripts when funcitonality is validated.

This is derived solely from files/history—no assumptions. Update as needed.