# Query & Retrieval – Technical Spec

## Core Responsibility
Process user queries to return sourced answers using chunk vector search and (optionally) knowledge graph search, with strict tenant/project/user scoping and low-latency paths.

## API Entry
- `routers/query_router.py`
  - `POST /api/query`: calls `QueryService.process_query`.
  - `POST /api/query/vector-search-test`: calls `SearchService.semantic_search` for diagnostics.

## Query Pipeline (Chunk-based)
- `services/queries/query_service.QueryService.process_query`:
  1) Persist query and placeholder response (`QueryRepository`).
  2) Build message history with optional project summary (`ProjectSummaryRepository`).
  3) Use `ClauseFormer` (LangChain/Anthropic) to decompose and answer via tools.
     - Tooling comes from `infrastructure.ai.tools` (search_chunks, etc.).
  4) Join clause statements into response; persist response text/status and source attributions.
  5) Errors roll back session and mark response failed.
- `services/search/search_service.SearchService`:
  - Generates embeddings via `Embedder`.
  - Calls `SearchRepository.semantic_search` → vector store search (tenant/project/user filtered).
  - Optional LLM rerank chain (Anthropic) to rescore candidates.

## KG Query Pipeline (optional)
- `QueryService.process_query_kg`:
  - Uses `SubquestionDecomposer` to create subquestions.
  - Invokes KG search tool (`infrastructure/ai/tools/kg_search_tools.search_knowledge_graph`) for each subquestion.
  - Summarizes facts via `ResponseSummarizer`; returns clauses with provenance.
- KG search tool:
  - Embeds query, uses `KnowledgeEventRepository.semantic_search` (statement embeddings) scoped by tenant/project.
  - Builds payload with statements, validity windows, doc/chunk provenance.

## Vector Store Behavior
- `infrastructure/vector_store` factory selects pgvector or Milvus backend.
- Search filters by tenant_id, project_ids, and user_id (documents created_by_user_id enforced in queries).
- Embedding dimension expected to match settings (`EMBEDDING_VECTOR_DIM` / Milvus config).

## Tenancy & Security
- All services receive `ContextScope`; repositories enforce tenant/project filters.
- Query results filtered to documents owned by `context.user_id` in vector store queries.

## Performance Posture
- Aim for low latency: main chunk-search path avoids LLM postprocessing unless rerank enabled.
- KG path involves embedding + DB search; summarization uses LLM and is slower—keep behind explicit usage.

## Gaps / TODO
- Role-based authorization not implemented (scope-only).
- No caching for repeated queries.
- KG search relies on Postgres KG; will pivot to Graphiti—interface/flag needed for swap.
