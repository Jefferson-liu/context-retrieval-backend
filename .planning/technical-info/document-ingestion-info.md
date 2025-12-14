# Document & Thread Ingestion – Technical Spec

## Core Responsibility
Persist documents and text threads, chunk/contextualize them, generate embeddings, push to vector store, and optionally extract knowledge graph facts with provenance and summaries.

## Key Components
- `services/document/processing.DocumentProcessingService`
  - Orchestrates upload/update/delete.
  - Uses `DocumentRepository`, `ChunkRepository`, `create_vector_store`, `KnowledgeGraphService`, `DocumentSummaryService`, `ProjectSummaryService`, `GitService`, `CommitMessageService`, `DocumentFileService`.
  - Chunking via `infrastructure/ai/chunking.Chunker` (Markdown-aware, recursive character splitter; chunk_size=512, overlap=20).
  - Embedding via `infrastructure/ai/embedding.Embedder` (BAAI/llm-embedder locally; OpenAI `text-embedding-3-small` when `local=False`).
- `services/text_thread/text_thread_service.TextThreadService`
  - Accepts Slack-style threads (messages list); stores thread as JSON-lines text, chunks it, and runs knowledge extraction.
- `KnowledgeGraphService`
  - Called from ingestion to extract events/triplets/entities and handle invalidation.
- `create_vector_store`
  - Selects pgvector or Milvus backend to upsert embeddings and serve search.

## Data Flow (Document Upload)
1) `upload_document` (router → DocumentProcessingService.upload_and_process_document):
   - Create document row (tenant/project/user scoped).
   - `process_document`:
     - Chunk text.
     - Contextualize each chunk with Embedder (LLM).
     - Create chunk rows.
     - Embed concatenated context+content (`local=False` → OpenAI) and upsert into vector store (tenant/project scoped).
     - Invoke `KnowledgeGraphService.refresh_document_knowledge` (invalidation off during initial upload).
     - Generate document summary and update project summary.
   - Persist file to disk + optional git commit.
2) `update_document`:
   - Overwrite document content, delete old chunks/vectors, reprocess as above, and commit git change.
3) `delete_document`:
   - Soft knowledge cleanup by calling `refresh_document_knowledge` with empty content, delete vectors/chunks/document, remove file, update project summary, optional git commit.

## Data Flow (Text Thread Ingestion)
- `TextThreadService.upload_text_thread`:
  - Stores thread (owner user, source system, external_thread_id).
  - Chunks JSON-lines text into document-backed chunks.
  - Calls `KnowledgeGraphService.refresh_text_thread_knowledge` for extraction and optional invalidation.

## Tenancy / Scope
- All repos invoked with `ContextScope`; vector store operations include tenant_id, project_ids, and user_id for filtering.
- Provenance: chunk/doc entities carry tenant/project; thread storage includes owner_user_id and source_system/external_thread_id.

## Performance Notes
- Parallelism capped (semaphores) for contextualization and embedding to avoid overload.
- Low-latency requirement: query path should avoid LLM; ingestion can use LLMs asynchronously.

## Gaps / TODO
- No role-based permissions beyond scope filtering.
- Embedding model/config is static; re-embedding strategy for model changes not defined.
- Git/versioning optional; error handling on git failures falls back to logging.
