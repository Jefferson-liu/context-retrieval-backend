# Milestone: Intent Resolver & Terminology Intelligence

## Goal
Determine the correct tenant/project context for every query by combining user signals, conversation history, and knowledge graph aliases, preventing data leakage and improving answer relevance.

## Dependencies
- Multi-tenant data model (`tenants`, `projects`, `user_project_roles`).
- `knowledge-graph.md` plan for alias management (`entity_aliases`).
- Conversation/session tracking (existing or to be added) to capture recent context.

## Deliverables
- `IntentResolverService` with API to resolve `(tenant_id, project_id)` given user/request metadata.
- Synonym dictionary storage and management endpoints (alias CRUD per project).
- Middleware/hooks in query endpoint to enforce resolved context.
- Telemetry on resolution confidence and overrides.

## Data & Schema
- `project_context_preferences`: stores user-selected default project, last used project, manual overrides.
- `intent_resolution_events`: logs inputs, chosen project, confidence score, resolver path.

## Services & APIs
- Resolver inputs: authenticated user, optional explicit project, conversation transcript, entity hints from query.
- Resolver outputs: `(tenant_id, project_id, confidence, rationale)`.
- Admin endpoints to manage aliases and escalate conflicts.

## Implementation Steps
1. Define resolver interface + DTOs.
2. Implement rule-based pipeline: explicit overrides → user defaults → entity alias match → fallback (prompt user).
3. Integrate with knowledge graph alias lookup (matching synonyms like "client" ↔ "salesperson").
4. Update `POST /api/query` to call resolver before search; reject if no project is chosen.
5. Log resolution events and expose metrics dashboard.
6. Provide admin UI/CLI to manage synonyms and inspect resolution history.
7. Write documentation for fallback UX (e.g., prompt front-end to ask user which project they meant).

## Testing & Validation
- Unit tests for resolver logic covering explicit selection, alias match, ambiguous cases.
- Integration tests ensuring query requests without project context trigger resolver and apply correct filters.
- Security tests verifying users cannot access projects they lack roles for.

## Observability
- Metrics: resolution confidence distribution, fallback frequency, alias coverage.
- Alerts for repeated low-confidence resolutions or unauthorized access attempts.

## Risks & Mitigations
- **Ambiguity**: Provide UI prompts when resolver is uncertain; log for training future ML model.
- **Alias sprawl**: add governance workflow (tie into knowledge graph plan) to review new aliases.

## Exit Criteria
- Resolver active in staging with audit logs and opt-in UI messaging.
- Query results scoped correctly across multi-project users.
- Documentation for developers + support teams on how context is resolved.

## Follow-On Work
- Incorporate ML model for intent classification once labeled data exists.
- Personalize resolver using user role metadata (e.g., support vs. product manager).
