- **Conflict Resolution Loop**: Detection stage only surfaces conflicting assertions; human reviewers select the canonical truth and the system updates graph + source documents accordingly, while still keeping the door open for future auto-resolution heuristics.
# Memory Layer Knowledge Base – Backend Vision

## Mission
Build a reliable, auto-updating memory layer that product-facing assistants can query when they need authoritative context about the product. The system ingests heterogeneous docs, tracks their provenance, resolves conflicts, and serves ranked snippets suitable for LLM consumption.

## Milestone Workstreams
- `.planning/milestone-vector-store-gateway.md` – abstraction + dual-write path for pgvector → Milvus (active draft: `.planning/draft-milvus-prototype.md`).
- `.planning/milestone-query-response-payload.md` – structured responses with sentence-level citations.
- `.planning/milestone-document-editing-service.md` – editable source workflow with reprocessing + git integration.
- `.planning/milestone-intent-resolver.md` – query context resolution and terminology intelligence.
- `.planning/milestone-conflict-review-workflow.md` – detection + manual resolution loop for conflicting assertions.
- `.planning/milestone-multi-tenant-data-layer.md` – tenant/project isolation across data and access layers (active draft: `.planning/draft-multi-tenant-data-layer.md`).

## Core Capabilities
- **Document Intake**: Async API for uploading product specs, release notes, tickets, chat transcripts; automatic chunking and embedding.
- **Semantic Retrieval**: Vector search over contextualized chunks, with metadata filters (version, domain, audience).
- **Version Awareness**: Track when knowledge changes, including temporal validity and git history of source documents.
- **Conflict Resolution**: Detect contradictory statements, surface candidate conflicts for human review, and mark deprecated knowledge.
- **Explainability**: Provide traceable sources, including document version, commit hash, and edit history.
- **Knowledge Graph Evolution**: Auto-generate and maintain a graph of entities, relationships, and assertions independent of source documents so insights can survive document churn.

## Architectural Pillars
1. **Ingestion Pipeline**
   - DocumentProcessingService orchestrates storage → chunking → embedding.
   - Future enrichment: classifiers (domain tagging, document type), entity extraction, summary generation.
2. **Knowledge Store**
   - PostgreSQL currently persists documents, metadata, and serves as the transactional store; embeddings sit in pgvector for now but retrieval APIs must remain store-agnostic so we can migrate to Milvus (preferred long-term vector DB) without rewriting callers.
   - Introduce a `VectorStoreGateway` abstraction with drivers for pgvector → Milvus to isolate vendor differences (index management, upsert semantics, filtering capabilities).
   - Partition all persistence layers by `tenant_id` and `project_id` while allowing users to belong to multiple projects; every document, chunk, assertion, and response row carries these columns to enforce row-level security.
   - Maintain a 1:1 mapping between `chunks` and their embedding vectors; vector primary keys mirror `chunk_id` so deletes/updates stay deterministic.
   - Chunk ownership is immutable: once a chunk is assigned to a tenant/project/user, it never transfers to another; edits happen in place within the same scope.
   - Flagged considerations: Milvus collections/partitions should align with `(tenant_id, project_id)` for isolation, and we need a background job to ensure embeddings stay consistent after chunk edits or schema migrations (see `milestone-vector-store-gateway.md`).
   - Plan to extend schema with `knowledge_assertions`, `knowledge_entities`, `knowledge_edges`, `versions`, `conflict_flags` while keeping embeddings externalized behind the gateway.
3. **Retrieval Layer**
   - QueryService receives question, embeds, searches, ranks, constructs response.
   - Future ranking: recency boosts, manual pinning, quality scores.
4. **Versioning & Provenance**
   - Current: basic git commits tied to document lifecycle.
   - Target: knowledge graph of assertions with validity intervals, pointer to original source file+commit and per-tenant lineage.
5. **Governance**
   - Admin tooling (CLI/API) for curating conflicts, approving replacements, rolling back.
   - Multi-tenant policy enforcement so admins only view the tenants/projects they administer; leverage database row-level security plus service-layer ACL checks.

6. **Knowledge Graph Layer** *(see `.planning/knowledge-graph.md` for full plan)*
   - High-level mandate: maintain tenant-scoped entities, relationships, and assertions decoupled from documents.
   - Graph services enrich retrieval and intent resolution while respecting `(tenant_id, project_id)` boundaries.

## Query Experience (PM Assistant)
- **Primary Contract**: `POST /api/query` accepts natural language questions, returns structured payload `{ response_text, citations[] }`.
- **Response Generation Path**
   1. QueryService logs query + placeholder response row.
   2. Embedding + semantic search returns top chunks (with doc_id, chunk_id, similarity).
   3. LLM synthesis layer (`AnswerComposerService`) consumes ranked chunks, crafts final answer, and emits per-sentence citation map.
   4. Citations reference `chunk_id` plus token-span offsets (start/end char indices) so the UI can highlight exact sentences.
- **Payload Shape**
   ```json
   {
      "response": {
         "text": "...",
         "segments": [
            {"text": "sentence", "citations": ["chunk:123#0-45"]}
         ]
      },
      "sources": [
         {"chunk_id": 123, "doc_id": 10, "doc_name": "release_notes.md", "content": "..."}
      ]
   }
   ```
- **Traceability**: store citation mappings in `response_citations` table to support audit, replay, and knowledge drift analysis. Detailed implementation steps live in `milestone-query-response-payload.md`.

## Editable Source Workflow *(see `milestone-document-editing-service.md`)*
- **Goal**: allow PMs to edit cited passages (sentence/paragraph level) directly from assistant UI.
- **Proposed Services**
   - `SourceSnippetService` to fetch chunk content plus contextual window (preceding/following sentences).
   - `DocumentEditingService` to apply edits by updating raw content, re-running chunk contextualization + embeddings (via queue-friendly reprocessing jobs), and triggering git commit with custom message.
   - `CitationRefreshJob` regenerates affected response entries or flags them for revalidation when underlying chunks change.
- **Granularity Strategy**
   - Maintain `chunk_sentences` table splitting each chunk into sentences with offsets.
   - When editing, locate sentence rows, apply diff to raw document, then rebuild chunk + embedding to maintain vector integrity.
   - Persist `sentence_revision_history` with links back to doc version & git commit for provenance.
- **Editing Flow**
   1. Assistant provides citation(s) for a sentence.
   2. UI calls SourceSnippetService → returns editable text + metadata.
   3. PM edits text, submits via DocumentEditingService.
   4. Service updates document, reprocesses chunk, commits change (`Update document: ...`), and invalidates/refreshes cached responses.
   5. Conflict detector reviews whether updated statement contradicts existing assertions.

## Multi-Tenant Context Awareness *(see `milestone-multi-tenant-data-layer.md` & `milestone-intent-resolver.md`)*
- **Tenant & Project Model**: Introduce `tenants`, `projects`, and `user_project_roles` tables. Documents and knowledge artifacts carry both identifiers to prevent data leakage while letting a user operate across multiple products.
- **Row-Level Security**: Enforce `(tenant_id, project_id)` filters at the repository layer and, where supported, at the database level (PostgreSQL RLS) to guarantee isolation.
- **Context Resolver**: `IntentResolverService` maps user utterances to the appropriate project by blending:
   - recent conversation signals,
   - explicit user selection (if provided), and
   - entity alias matching within the knowledge graph.
- **Terminology Intelligence**: Maintain per-project synonym dictionaries so terms like "salesperson" and "client" resolve to the same entity node when appropriate (details in `knowledge-graph.md`).
- **Access Audit Trail**: Log every retrieval/edit action with tenant/project context to detect misconfiguration or attempted cross-tenant access.

## Performance Considerations
- **Incremental Reprocessing**: Editing a snippet should only re-chunk and re-embed the impacted segments; batch updates enqueue background jobs so the UI remains snappy.
- **Vector Store Migration**: Ensure insertion/search paths speak through the `VectorStoreGateway` so swapping pgvector for Milvus is configuration-only; mirror data during migration to avoid downtime.
- **Embedding Warm Cache**: Maintain an embedding model pool and consider caching recent vectors to minimize cold-start latency during bulk edits.
- **Chunk Edit Throughput**: Track queue depth and processing SLA; autoscale worker count when the backlog grows (e.g., during large doc rewrites).

## Open Questions
- How to represent conflicting assertions? (options: truth tables, multi-valued flags, per-entity timelines)
- Retention policy for outdated knowledge—archive vs. delete vs. mark as superseded.

## Success Criteria
- Product managers get consistent answers even as features evolve.
- Assistant can cite up-to-date sources with clear provenance.
- Ingestion of new docs auto-updates relevant knowledge without manual rework.
- Conflicts detected/triaged within agreed SLA.
