# Milestone: Multi-Tenant Data Layer & Access Controls

## Goal
Embed tenant/project isolation across the data stack so users only see their product data while supporting multi-project assignments and shared infrastructure.

## Dependencies
- Existing document/chunk schema in PostgreSQL.
- Authentication/authorization context providing user identity.
- Planned resolver work (`milestone-intent-resolver.md`).

## Deliverables
- Database migrations adding `tenant_id` + `project_id` to documents, chunks, queries, responses, assertions (where missing).
- RLS policies in PostgreSQL enforcing `(tenant_id, project_id)` filters.
- Repository layer updates to require context parameters.
- Seed scripts for tenants/projects and role assignments.
- Automated tests verifying isolation and access patterns.

## Data & Schema
- Tables: `tenants`, `projects`, `user_project_roles` (with role enumeration).
- Indexes on `(tenant_id, project_id)` for high-traffic tables.
- Default tenant/project values prevented; migrations fail if null.

## Services & APIs
- Middleware extracts user context and populates `RequestContext` with allowed `(tenant_id, project_id)` set.
- Repository methods accept context and apply filters automatically.
- Admin endpoints to manage project membership.

## Implementation Steps
1. Design migration path (backfill existing records with `default` tenant/project; plan to split later).
2. Create tables + migrations for tenancy core and add columns to existing tables.
3. Implement RLS policies (select/insert/update/delete) referencing current_user or session config.
4. Update SQLAlchemy models and repositories to include new fields.
5. Ensure vector store gateway receives tenant/project metadata for partitioning.
6. Write integration tests ensuring cross-tenant access is blocked.
7. Document operational steps for onboarding new tenants/projects.

## Testing & Validation
- Unit tests for repository queries verifying filters applied.
- Integration tests using multiple tenants to ensure isolation.
- Security audits (static + runtime) confirming RLS + service-layer checks.

## Observability
- Metrics: unauthorized access attempts, tenant/project counts, latency per tenant.
- Logging includes tenant/project IDs for traceability (avoid PII exposure).

## Risks & Mitigations
- **Backfill mistakes** → run migrations in dry-run with backups; add validation scripts comparing counts.
- **RLS complexity** → keep policies simple; use helper functions to set session variables.

## Exit Criteria
- Multi-tenant schema deployed to staging with passing tests.
- All repository calls require tenant/project context.
- Operations runbook updated for tenant onboarding.

## Follow-On Work
- Support tenant-level configuration (e.g., custom embeddings) in future milestones.
- Add billing/usage tracking per tenant.
