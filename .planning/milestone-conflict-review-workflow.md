# Milestone: Conflict Detection & Manual Review Loop

## Goal
Surface conflicting assertions to reviewers, capture the human-approved canonical truth, and propagate updates to the knowledge graph and source documents.

## Dependencies
- Knowledge graph foundation (`knowledge-graph.md`).
- Assertion extraction pipeline generating candidate statements.
- `milestone-document-editing-service.md` for applying document updates.

## Deliverables
- Conflict detection job comparing new assertions vs. active ones within the same entity scope.
- `conflicts` table storing assertion sets, status, reviewer metadata.
- Reviewer endpoints/UI workflow for listing conflicts, viewing evidence, and selecting the correct assertion.
- Automation to update `knowledge_assertions`, archive superseded assertions, and trigger document edits if required.
- Audit logging + notifications for conflict resolution events.

## Data & Schema
- `conflicts`: `id`, `tenant_id`, `project_id`, `entity_id`, `status`, `created_at`, `resolved_at`.
- `conflict_assertions`: join table linking conflict to candidate assertions with metadata (similarity score, source chunk, commit hash).
- Extend `knowledge_assertions` with `superseded_by_conflict_id` for traceability.

## Services & APIs
- Detection job runs after ingestion/editing; uses vector/semantic comparison + rules to flag contradictions.
- Reviewer API: `GET /api/conflicts`, `GET /api/conflicts/{id}`, `POST /api/conflicts/{id}/resolve` (payload includes chosen assertion + optional edited text request).
- Notification hook (email/slack/webhook) when new conflicts arise.

## Implementation Steps
1. Define contradiction heuristics (e.g., antonym detection, numeric mismatch thresholds).
2. Build detection worker that queues conflicts with supporting evidence.
3. Implement persistence layer + repositories for conflicts and mappings.
4. Develop reviewer endpoints with RBAC (only authorized roles can resolve).
5. On resolution, update selected assertion status to `active`, others to `deprecated`, and push optional doc edit tasks to editing service.
6. Write audit + telemetry hooks capturing action details.
7. Create reviewer UI (or CLI stub) for early adopters.

## Testing & Validation
- Unit tests for heuristic functions (contradiction detection, threshold handling).
- Integration tests simulating conflict creation and resolution end-to-end.
- Security tests ensuring only permitted users can resolve conflicts.

## Observability
- Metrics: conflicts created/resolved per project, average resolution time, auto-detected false positives.
- Alerts when conflicts remain unresolved past SLA.

## Risks & Mitigations
- **False positives** → allow reviewers to dismiss conflicts with reason; feed back into heuristics tuning.
- **Reviewer fatigue** → prioritize conflicts by severity/impact, batch notifications.

## Exit Criteria
- Conflict workflow live in staging with sample data.
- Reviewers can resolve conflicts and see updates reflected in queries within expected latency.
- Documentation covers heuristics, reviewer playbook, and rollback procedures.

## Follow-On Work
- Add optional auto-resolution for high-confidence cases.
- Integrate with analytics dashboards for governance reporting.
