# Tenancy & Auth Context (current code)

## Core Responsibility
Enforce per-tenant and per-project scoping for all DB access; accept external user/product identity and roles from an upstream auth service (roles currently placeholders).

## Entry Points & Scope Resolution
- `routers/dependencies.get_request_context_bundle`:
  - Reads headers `user_id` and `project_id` (required unless in dev/default mode).
  - Looks up user-project roles via `UserProjectRoleRepository`; enforces user belongs to exactly one tenant.
  - Builds `ContextScope(tenant_id, project_ids, user_id)` and registers scope in Postgres via `set_app_context`.
  - Dev mode: optional default user/project bootstrap via `DevPlaceholderBootstrapper` when `settings.IS_DEV_MODE`.
- `ContextScope` (infrastructure/context.py):
  - Holds `tenant_id`, `project_ids`, `user_id`; `primary_project()` returns the first project.
- All repositories and services receive `ContextScope` and are expected to filter queries using it.

## Database Enforcement
- RLS function `set_app_context` and policies created in `infrastructure/database/setup.configure_multi_tenant_rls`.
- Tables under RLS: documents, chunks, embeddings, queries, responses, sources, knowledge_* (entities/relationships/statements/triplets), document_summaries, project_summaries, user_products.
- Policies require matching `tenant_id` and `project_id` (or project list) from current settings; both USING and CHECK are enforced.
- `seed_default_tenant_and_project` seeds default tenant/project and default user role (`DEFAULT_USER_ID` / `DEFAULT_USER_ROLE`).

## API Surface
- All routers depend on `get_request_context_bundle` (Document, Query, Knowledge, User).
- API key guard via `routers.dependencies.require_api_key` when `settings.API_AUTH_TOKEN` is set.

## Role Handling (placeholder)
- Roles come from `UserProjectRole` records; enforcement today is limited to membership checks (e.g., user must belong to requested project).
- No fine-grained permissions yet; future roles/permissions will come from external auth service.

## Multi-product vs tenant-only
- Current behavior: per-tenant + per-project scoping (project is effectively product).
- Keep option open to treat product as metadata: would relax project filtering in policies and scope to tenant-only; code currently assumes project list in scope.

## Cross-Cutting Expectations
- No cross-tenant/project leakage: every query/path must pass `ContextScope` to repositories/services.
- External auth owns user/product identity; we store only IDs needed for scoping and provenance.
