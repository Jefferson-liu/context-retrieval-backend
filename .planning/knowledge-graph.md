# Knowledge Graph Architecture Plan

## Mission
Deliver a tenant-aware knowledge graph that evolves independent of raw documents, capturing entities, relationships, and assertions so downstream assistants can reason about product knowledge with strong provenance guarantees.

## Guiding Principles
- **Document-Decoupled**: Insights persist even when source documents change or are archived.
- **Tenant Isolation**: Every node and edge is scoped by `tenant_id` and `project_id`; cross-tenant access is impossible by design.
- **Explainable**: Each assertion traces back to the originating document, chunk, and git commit.
- **Incremental Updates**: Edits reflow into the graph quickly without full reprocessing.
- **Context-Aware**: Synonyms, aliases, and intent signals resolve to the right project-specific concepts.

## High-Level Flow
1. **Ingestion**: Document pipeline stores metadata + content and emits structured chunks.
2. **Extraction**: `AssertionExtractionService` normalizes statements (entity, relation, attributes) and pushes deltas to the graph queue.
3. **Graph Update**: `KnowledgeGraphService` applies upserts to entities/edges, recording provenance and temporal validity.
4. **Retrieval**: Query layer joins vector results with graph insights for richer answers.
5. **Monitoring**: Drift/conflict detectors monitor assertions for contradictions or stale relationships.

## Data Model
- **Tenancy Core**
  - `tenants(id, name)`
  - `projects(id, tenant_id, name, status)`
  - `user_project_roles(user_id, project_id, role, permissions)`
- **Graph Tables**
  - `knowledge_entities(id, tenant_id, project_id, canonical_name, type, attributes, created_at, updated_at)`
  - `entity_aliases(id, tenant_id, project_id, entity_id, alias, locale, confidence)`
  - `knowledge_assertions(id, tenant_id, project_id, entity_id, relation, object_entity_id, literal_value, validity_start, validity_end, source_chunk_id, source_commit_hash, confidence, status)`
  - `knowledge_edges(id, tenant_id, project_id, subject_entity_id, predicate, object_entity_id, weight, created_at, updated_at)`
  - `assertion_metadata(assertion_id, embedding_vector_id, extraction_method, reviewer_id, review_status)`
- **Supporting Structures**
  - `graph_change_queue` for asynchronous processing.
  - Materialized views for fast lookup (e.g., entity -> latest assertions).

## Access Control
- Apply PostgreSQL Row-Level Security on every graph table keyed by `(tenant_id, project_id)`.
- Service-layer repositories always filter by `tenant_id` + `project_scope` derived from authenticated session.
- Audit table `graph_access_log` captures read/write operations for compliance.

## Synchronization with Documents
- Chunks include `tenant_id`, `project_id`, and `chunk_id`; assertions reference these for provenance.
- When documents are edited, `DocumentEditingService` enqueues affected chunk IDs; workers recompute assertions and update graph nodes/edges.
- Git metadata (`commit_hash`, `author`, `message`) travels with extraction jobs so reviewers can trace changes.

## Intent Resolution & Terminology
- `IntentResolverService` blends conversation context, explicit project selection, and entity alias matches to infer the correct project.
- Alias management supports per-project terminology (e.g., "client" vs. "salesperson") with conflict resolution workflows when aliases collide.
- Future enhancement: embed entity descriptions for semantic alias matching using the vector store abstraction.

## Query Integration
- Retrieval pipeline pulls top vector hits, maps `chunk_id` -> `knowledge_assertions`, and decorates responses with structured graph insights.
- Provide optional graph-only queries (e.g., dependency lookups, timeline views) for admin tooling.
- Ensure APIs accept tenant/project context explicitly to avoid accidental leakage.

## Operations & Performance
- Horizontal scale via partitioned tables (`tenant_id`, `project_id`) and read replicas for analytics queries.
- Cache alias resolutions and popular entity neighborhoods per project.
- Batch graph updates in the queue but flush high-priority edits synchronously for user-facing edits.
- Expose metrics: graph update latency, assertion churn rate, synonym coverage.

## Conflict Resolution Strategy
- Detection layer surfaces conflicting assertion sets to reviewers with linked source metadata.
- Human decision is authoritative: reviewers mark the correct assertion, which updates `knowledge_assertions`, adjusts document content when necessary, and archives superseded statements.
- Preserve hooks for future automated resolution (confidence thresholds, policy rules) but keep them disabled until we have guardrails.

## Open Questions
- Should we support cross-project shared ontologies within a tenant?
- How do we capture hierarchy/ownership (e.g., product -> feature -> KPI) without overcomplicating the schema?
- What governance process approves alias or assertion changes that affect multiple teams?
