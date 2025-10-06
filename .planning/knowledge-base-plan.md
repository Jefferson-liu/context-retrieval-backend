- **Conflict Resolution Loop**: Detection stage only surfaces conflicting assertions; human reviewers select the canonical truth and the system updates graph + source documents accordingly, while still keeping the door open for future auto-resolution heuristics.
# Memory Layer Knowledge Base – Backend Vision

## Mission
Build a reliable, auto-updating memory layer that product-facing assistants can query when they need authoritative context about the product. The system ingests heterogeneous docs, tracks their provenance, resolves conflicts, and serves ranked snippets suitable for LLM consumption.

## Milestone Workstreams (Active)
- `.planning/milestone-lean-core-refactor.md` – strip non-essential integrations (Milvus, git mirroring) and harden the pgvector-only baseline.
- `.planning/milestone-dual-lane-retrieval.md` – add sentence hashing, lexical indexing, fusion retrieval, and background embedding mechanics.
- `.planning/milestone-safe-agentic-controller.md` – deliver SAFE clause generation with IRCoT reasoning, verification, and clause-level persistence.

### Archived / On Hold
- `.planning/milestone-query-response-payload.md`
- `.planning/milestone-document-editing-service.md`
- `.planning/milestone-intent-resolver.md`
- `.planning/milestone-conflict-review-workflow.md`

These legacy milestones remain as reference material but are superseded by the SAFE + IRCoT roadmap above.

## Core Capabilities
- **Document Intake**: Async API for uploading product specs, release notes, tickets, chat transcripts; automatic chunking and embedding.
- **Semantic Retrieval**: Vector search over contextualized chunks, with metadata filters (domain, audience, project scope).
- **Conflict Resolution**: Detect contradictory statements, surface candidate conflicts for human review, and mark deprecated knowledge.
- **Explainability**: Provide traceable sources, including current chunk metadata and optional git commit identifiers when available.
- **Knowledge Graph Evolution**: Auto-generate and maintain a graph of entities, relationships, and assertions independent of source documents so insights can survive document churn.

## Architectural Pillars
1. **Ingestion Pipeline**
   - DocumentProcessingService orchestrates storage → chunking → embedding.
   - Future enrichment: classifiers (domain tagging, document type), entity extraction, summary generation.
2. **Knowledge Store**
   - PostgreSQL currently persists documents, metadata, and serves as the transactional store; embeddings sit in pgvector for now but retrieval APIs must remain store-agnostic so we can migrate to Milvus (preferred long-term vector DB) without rewriting callers.
   - Keep vector store integration behind a thin abstraction so swapping providers (pgvector vs. Milvus) remains a configuration choice.
   - Partition all persistence layers by `tenant_id` and `project_id` while allowing users to belong to multiple projects; every document, chunk, assertion, and response row carries these columns to enforce row-level security.
   - Maintain a 1:1 mapping between `chunks` and their embedding vectors; vector primary keys mirror `chunk_id` so deletes/updates stay deterministic.
   - Chunk ownership is immutable: once a chunk is assigned to a tenant/project/user, it never transfers to another; edits happen in place within the same scope.
   - Flagged considerations: Milvus collections/partitions should align with `(tenant_id, project_id)` for isolation, and we need a background job to ensure embeddings stay consistent after chunk edits or schema migrations when we eventually standardize on a single store.
   - Plan to extend schema with `knowledge_assertions`, `knowledge_entities`, `knowledge_edges`, `conflict_flags` while keeping embeddings externalized behind the gateway.
3. **Retrieval Layer**
   - QueryService receives question, embeds, searches, ranks, constructs response.
   - Future ranking: recency boosts, manual pinning, quality scores.
4. **Provenance**
   - Current: optional git commits tied to document lifecycle; database stores only the latest chunk state.
   - Target: knowledge graph of assertions pointing to active chunks and, when available, associated git commits.
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
- **Deletion Handling**: when a cited chunk is removed, update the related citation to set `chunk_id`/`doc_id` to `NULL` while retaining the textual snippet for transparency.

## Editable Source Workflow *(see `milestone-document-editing-service.md`)*
- **Goal**: allow PMs to edit cited passages (sentence/paragraph level) directly from assistant UI.
- **Proposed Services**
   - `SourceSnippetService` to fetch chunk content plus contextual window (preceding/following sentences).
   - `DocumentEditingService` to apply edits by updating raw content, re-running chunk contextualization + embeddings (via queue-friendly reprocessing jobs), and triggering git commit with custom message.
   - `CitationRefreshJob` regenerates affected response entries or flags them for revalidation when underlying chunks change.
- **Granularity Strategy**
   - Maintain `chunk_sentences` table splitting each chunk into sentences with offsets.
   - When editing, locate sentence rows, apply diff to raw document, then rebuild chunk + embedding to maintain vector integrity.
   - Persist only the latest sentence record and optionally tag it with the git commit that introduced the change.
- **Editing Flow**
   1. Assistant provides citation(s) for a sentence.
   2. UI calls SourceSnippetService → returns editable text + metadata.
   3. PM edits text, submits via DocumentEditingService.
   4. Service updates document, reprocesses chunk, commits change (`Update document: ...`), and invalidates/refreshes cached responses.
   5. Conflict detector reviews whether updated statement contradicts existing assertions.

## Multi-Tenant Context Awareness *(see `milestone-intent-resolver.md`)*
- **Tenant & Project Model**: `tenants`, `projects`, and `user_project_roles` tables now back every document and knowledge artifact so users only view their scoped data.
- **Row-Level Security**: `(tenant_id, project_id)` filters run through both repository checks and PostgreSQL RLS to guarantee isolation.
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
