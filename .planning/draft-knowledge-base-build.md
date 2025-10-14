# Knowledge Base Build – Draft Plan

## Purpose & Context
- Establish a durable knowledge base that supports retrieval-augmented assistants with auditable, up-to-date product knowledge.
- Extend the current ingestion + retrieval stack (pgvector-backed) into a multi-layer memory system with governance, conflict resolution, and downstream API guarantees.
- Align the plan with existing roadmaps (`knowledge-base-plan.md`, SAFE clause generation) while adding concrete implementation phases for net-new knowledge base features.

## Goals
1. Provide a single, tenant-scoped source of truth for facts, decisions, and historical context.
2. Support both human-authored content and machine-extracted assertions with provenance.
3. Expose low-latency query surfaces suitable for LLM-augmented assistants (JSON payloads, streaming events).
4. Maintain conflict tracking and review workflows so knowledge stays trustworthy.
5. Ship incrementally—deliver a minimal, useful baseline in Phase 1, then layer advanced capabilities.

## Out-of-Scope (for this initial program)
- Cross-tenant analytics dashboards.
- Automated document redaction or classification pipelines.
- End-user UI; assume API-first delivery with basic admin CLI/tooling.
- Hard real-time synchronization with external systems (e.g., Jira, Confluence) beyond batch ingestion jobs.

## Assumptions
- PostgreSQL + pgvector remain the storage baseline for Phase 1; Milvus migration handled in parallel roadmap.
- `tenant_id` + `project_id` columns exist on all knowledge artifacts and RLS is enforced at the database layer.
- LLM provider remains configurable via `config/settings.py` (Anthropic / OpenAI); structured output is achievable with current models.
- Existing ingestion services (`DocumentProcessingService`, `SearchService`) remain intact and can be extended, not rewritten.

## Architecture Overview
1. **Ingestion Layer**
   - File upload API → chunking → embedding → knowledge assertion extraction jobs.
   - Background workers apply entity extraction + assertion synthesis using prompt templates.
   - Metadata tagging (doc type, lifecycle stage, owners) stored alongside documents.
2. **Knowledge Store**
   - New tables: `knowledge_entities`, `knowledge_assertions`, `assertion_sources`, `conflict_flags`.
   - **Knowledge Graph Tables**: `knowledge_entities` (nodes: people, products, concepts), `knowledge_relationships` (edges: links between entities with types like "works_on", "depends_on", metadata like confidence scores, timestamps), `relationship_metadata` (key-value pairs for additional attributes).
   - Chunks remain in `documents/chunks` tables; assertions reference chunks via foreign key and cache canonical text.
   - Versioning handled via soft-deletes + `valid_from/valid_to` columns.
3. **Governance & Review**
   - Conflict detection jobs compare overlapping assertions; flagged items routed to reviewers.
   - CLI/API endpoints to approve, reject, or merge assertions while preserving audit trail.
4. **Retrieval APIs**
   - `QueryService` evolves to pull statements from assertions (with fallbacks to chunks), returning citation payloads.
   - ClauseFormer integrates verified assertions into reasoned answers.
   - Future streaming channel emits knowledge updates to downstream consumers.
5. **Observability**
   - Metrics (ingestion throughput, assertion counts, conflict backlog) exposed via Prometheus endpoints.
   - Structured logs around assertion creation/update for audit.

## Phase Breakdown

### Phase 1 – Foundational Knowledge Schema & APIs (2-3 sprints)
- [ ] **Add graph schema**: `knowledge_entities` (id, name, type, tenant_id, project_id), `knowledge_relationships` (id, source_entity_id, target_entity_id, relationship_type, metadata_json), `relationship_metadata` (relationship_id, key, value).
- [ ] Extend ingestion pipeline to create placeholder assertions referencing chunks (no auto-extraction yet).
- [ ] Implement `KnowledgeAssertionRepository` with CRUD + conflict flag helpers.
- [ ] Add API endpoints (internal) to create/update assertions manually and list by tenant/project.
- [ ] Update `QueryService` to surface assertions when present, fallback to chunk content otherwise.
- [ ] Seed minimal admin CLI to review conflicts (basic accept/reject).
- [ ] Tests: unit coverage for repositories, ingestion path, and API contracts.

### Phase 2 – Automated Assertion Extraction & Conflict Detection (3-4 sprints)
- [ ] Introduce async workers (Celery/Arq) to process new chunks → run LLM extraction prompts.
- [ ] **Entity/Relationship Extraction**: Workers also extract entities and relationships from chunks, populating the graph tables with deduplication logic.
- [ ] Store extraction prompt versions + lineage metadata for traceability.
- [ ] Implement conflict detection heuristics (string similarity, negation cues, entity mismatches).
- [ ] Build reviewer queue endpoints and status tracking (pending, approved, rejected).
- [ ] Update QueryService to score/boost approved assertions; degrade confidence when under review.
- [ ] Expand ClauseFormer to request assertion snippets before falling back to raw chunk search.
- [ ] Tests: integration coverage for worker → DB, conflict detection accuracy.

### Phase 3 – Advanced Knowledge Operations (4+ sprints)
- [ ] Knowledge graph enrichment: link assertions to entities/relations (align with `knowledge-graph.md`).
- [ ] Temporal awareness: maintain assertion timelines, surface latest valid truth per entity.
- [ ] Observability dashboards (Grafana) for assertion volume, conflict SLA, retrieval hit rates.
- [ ] Subscription/streaming interface (WebSocket/SSE) for knowledge change events.
- [ ] Milvus dual-write (if vector migration completed) to ensure retrieval parity.
- [ ] DR/backup strategy for knowledge tables and assertion cache rebuild tooling.

## Risks & Mitigations
- **Model hallucinations during extraction** → add human review + confidence scoring; log prompts/responses.
- **Schema churn impacting existing services** → draft migrations in staging, keep repositories backward compatible until clients updated.
- **Performance regressions** → benchmark new joins, add indices on `(tenant_id, project_id, entity_id)`.
- **Reviewer backlog** → automate prioritization, add Slack/email notifications, monitor SLA metrics.

## Testing Strategy
- Unit tests for new repositories/services with in-memory (asyncpg) harness.
- Contract tests for API endpoints covering RBAC and RLS constraints.
- Integration tests simulating ingestion → assertion extraction → retrieval response flow.
- Load tests targeting ingestion throughput and query latency baselines.

## Observability & Tooling
- Extend existing logging to include assertion IDs and decision status.
- Prometheus metrics: `knowledge_assertions_total`, `knowledge_conflicts_open`, `assertion_latency_seconds`.
- Feature flag hooks to disable auto-extraction per tenant if issues arise.

## Rollout & Change Management
1. Deploy Phase 1 schema + manual assertion APIs to staging → production behind feature flag.
2. Pilot automated extraction with internal tenants only; collect precision/recall metrics before broad rollout.
3. Document operational playbooks (backfill, conflict resolution) in internal wiki.
4. Once stable, update `knowledge-base-plan.md` with outcomes and mark milestone complete.

## Open Questions
- Preferred worker framework (Celery vs. simple asyncio background tasks)?
- Do we need tenant-specific prompt templates for extraction (e.g., domain jargon)?
- How to reconcile assertions originating from external integrations (e.g., Jira) with manual uploads?
- What is acceptable SLA for conflict resolution (hours vs. days)?
- **Graph traversal service**: Planned separately for populating LLM with graph-derived context.

## Next Steps
- Socialize this draft with stakeholders (platform + PM leads).
- Convert Phase 1 tasks into GitHub issues with owners/estimates.
- Align with SAFE clause roadmap to share components (assertion validation, structured output).
- Update `.planning/knowledge-base-plan.md` after feedback is incorporated.
