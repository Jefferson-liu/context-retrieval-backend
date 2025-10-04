# Context Retrieval Backend

This backend provides document ingestion, embedding, and semantic search capabilities. It supports both PostgreSQL with pgvector and Milvus as vector stores.

## Quick start

```powershell
.venv\Scripts\activate
python main.py
```

## Milvus smoke test

A lightweight end-to-end smoke test is available to verify Milvus connectivity, ingestion, and search logic without requiring external embedding models.

```powershell
# Ensure VECTOR_STORE_MODE=milvus and Milvus/PostgreSQL are reachable
.venv\Scripts\activate
python scripts\milvus_smoke_test.py
```

This script injects a synthetic document, runs a semantic query, and (by default) cleans up the document and Milvus vectors afterward. Set `RUN_MILVUS_SMOKE_TESTS=1` to integrate the same check into the pytest suite.

## HTTP E2E smoke test (UAT)

To exercise the running FastAPI service end-to-end (upload → chunk → embed → Milvus search), first start the backend and then run:

```powershell
# Terminal 1 – start the API
.venv\Scripts\activate
python main.py

# Terminal 2 – execute the HTTP smoke test
$env:RUN_E2E_SMOKE_TESTS="1"
.venv\Scripts\activate
python -m pytest tests/test_end_to_end_smoke.py
```

The test will skip automatically if the API is unreachable. Ensure `MILVUS_VECTOR_DIM` matches the embedding model output (defaults to `768`) before running.
