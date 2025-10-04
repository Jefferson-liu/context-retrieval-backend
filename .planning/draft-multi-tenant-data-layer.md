# Draft: Multi-Tenant Data Layer & Access Controls

## Objective
Implement tenant/project isolation end-to-end so that every repository, service, and downstream subsystem scopes data access correctly for multi-product users while preserving backward compatibility during rollout.

## Deliverables
- Alembic migrations introducing `tenants`, `projects`, `user_project_roles`, and tenant/project foreign keys on existing domain tables.
- PostgreSQL Row-Level Security policies plus helper SQL function `set_app_context` for session scoping.
- Application-layer `ContextScope` DTO, request-context wiring, and repository updates enforcing scoped queries.
- Backfill script and feature flags to manage rollout without downtime.
- Unit + integration test coverage proving isolation and regression safety.

## Current State & Assumptions
- Database models now carry tenant/project/user metadata, and Alembic revision `20251003_multi_tenant_core` backfills existing rows to the seeded tenant/project pair.
- Auth middleware can expose the authenticated user ID; we will extend it to provide tenant/project context.
- Pgvector currently stores embeddings keyed by `chunk_id`; Milvus integration is pending but must receive tenant/project metadata after this milestone.
- Ownership of a chunk (tenant/project/user) is immutable once created; knowledge is never reassigned to a different tenant or user.
- Alembic history starts with `20251003_multi_tenant_core`; subsequent revisions must depend on it.

### Latest Progress — 2025-10-03
- ✅ Migration `20251003_multi_tenant_core` creates tenancy tables, adds FKs/indices, and backfills legacy data to the default tenant/project.
- ✅ RLS helper `set_app_context` plus policies are configured at runtime via `configure_multi_tenant_rls`; app startup seeds the default tenant/project/user role.
- ✅ Repository + service layers accept `ContextScope`, and request dependencies set session scopes before work. Added unit test coverage (`tests/test_multi_tenant_repositories.py`) to assert tenant isolation.
- ⏳ Remaining scope: fuller integration tests & docs/runbook updates. *(Dedicated backfill tooling no longer required because the Alembic revision seeds defaults; keep a note in rollout docs in case external data is imported in the future.) Pgvector-backed `VectorStoreGateway` now powers ingestion and search with tenant/project filters plus dedicated tests.*

### Terminology
- **Tenant** → the top-level organization or customer account (e.g., a company using the assistant platform).
- **Project** → a product/workstream under a tenant (e.g., specific app, vertical, or feature line the user manages).
- **User** → individual person with access to one or more projects inside a tenant; permissions derived from `user_project_roles`.

## Design Contracts
- Every data row touching user content carries `tenant_id` and `project_id` (non-null `Integer`, FK).
- `tenant_id` + `project_id` originate from `RequestContext`, not request payloads, to avoid spoofing.
- Chunk ownership (including `created_by_user_id`) is immutable—updates must preserve original tenant/project, and edits occur within that scope only.
- Row-Level Security (RLS) operates on PostgreSQL tables with policies referencing session variables (`app.current_tenant`, `app.current_projects`).
- Repositories accept a `ContextScope` DTO `{ tenant_id: int, project_ids: list[int] }` and must use it in every query filter.

## Implementation Plan
1. **Schema Migrations** *(Alembic revision `20251003_multi_tenant_core` – implemented)*
    - Create tables using auto-incrementing integers for consistency with existing models:
       ```sql
       CREATE TABLE tenants (
          id SERIAL PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          slug TEXT NOT NULL UNIQUE,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
       );
       CREATE TABLE projects (
          id SERIAL PRIMARY KEY,
          tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          slug TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          UNIQUE (tenant_id, slug)
       );
       CREATE TABLE user_project_roles (
          id SERIAL PRIMARY KEY,
          user_id TEXT NOT NULL,
          tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          role TEXT NOT NULL,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
          UNIQUE (user_id, project_id)
       );
       ```
    - Add `tenant_id`/`project_id` (`Integer`, `nullable=False`) to existing tables: `uploaded_documents`, `chunks`, `embeddings`, `queries`, `responses`, `sources`, `queries_history` (if present), future knowledge-graph tables. Example Alembic snippet:
       ```python
       op.add_column("uploaded_documents", sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"))
       op.add_column("uploaded_documents", sa.Column("project_id", sa.Integer(), nullable=False, server_default="1"))
       op.create_foreign_key("fk_docs_tenant", "uploaded_documents", "tenants", ["tenant_id"], ["id"], ondelete="RESTRICT")
       op.create_foreign_key("fk_docs_project", "uploaded_documents", "projects", ["project_id"], ["id"], ondelete="RESTRICT")
       op.create_index("ix_uploaded_documents_tenant_project", "uploaded_documents", ["tenant_id", "project_id"])
       # repeat for other tables (chunks, embeddings, queries, responses, sources)
       op.alter_column("uploaded_documents", "tenant_id", server_default=None)
       op.alter_column("uploaded_documents", "project_id", server_default=None)
       ```
   - Backfill existing rows to the seed tenant/project (`default/default`) before locking columns to `NOT NULL`.
   - Down migration drops foreign keys/columns and removes tenancy tables for rollback.

2. **Row-Level Security** *(implemented via `infrastructure/database/setup.py`)*
   - Enable RLS on each tenant-aware table.
   - Create policies:
     - `SELECT`: allow when `tenant_id = current_setting('app.current_tenant')` **and** `project_id = ANY (current_setting('app.current_projects')::uuid[])`.
     - `INSERT`/`UPDATE`: allow only if `tenant_id`, `project_id` match the current settings.
   - Helper function `set_app_context(tenant INT, project TEXT)` invoked at session start keeps session variables consistent (set today through router dependency).
   - Migration snippet (reference only — live implementation resides in startup hook):
       ```sql
       CREATE OR REPLACE FUNCTION set_app_context(p_tenant integer, p_projects integer[])
       RETURNS VOID AS $$
       BEGIN
          PERFORM set_config('app.current_tenant', p_tenant::text, true);
          PERFORM set_config('app.current_projects', array_to_string(p_projects, ','), true);
       END;
       $$ LANGUAGE plpgsql SECURITY DEFINER;

       ALTER TABLE uploaded_documents ENABLE ROW LEVEL SECURITY;
       CREATE POLICY uploaded_documents_tenant_project_rls ON uploaded_documents
          USING (
             tenant_id = current_setting('app.current_tenant')::integer
             AND project_id = ANY(string_to_array(current_setting('app.current_projects'), ',')::integer[])
          );
       -- repeat for chunks, embeddings, queries, responses, sources
       ```
    - When `ENFORCE_RLS` flag is true, run `ALTER TABLE ... FORCE ROW LEVEL SECURITY` during startup migration.

3. **Data Access Layer** *(implemented)*
    - Introduce `ContextScope` in `services/context.py`:
       ```python
       @dataclass
       class ContextScope:
             tenant_id: int
             project_ids: list[int]

             def primary_project(self) -> int:
                   if not self.project_ids:
                         raise ValueError("ContextScope.project_ids cannot be empty")
                   return self.project_ids[0]
       ```
    - Update repositories (e.g., `DocumentRepository`, `ChunkRepository`, `QueryRepository`) signatures to accept `context: ContextScope`. Example:
       ```python
       async def list_documents(self, context: ContextScope) -> list[UploadedDocument]:
             stmt = select(UploadedDocument).where(
                   UploadedDocument.tenant_id == context.tenant_id,
                   UploadedDocument.project_id.in_(context.project_ids),
             )
             return (await self.session.execute(stmt)).scalars().all()
       ```
    - Add helper assertion `ensure_scope(context)` inside base repository to prevent accidental omission.

4. **Middleware & Dependency Updates** *(implemented)*
   - Extend FastAPI dependency `get_db` or a new `get_request_context` to resolve allowed projects:
     - Read user ID from auth.
     - Lookup `user_project_roles` to derive permitted projects.
     - Set database session variables via `session.execute("SELECT set_app_context(:tenant, :projects)", ...)`.
     - Return `ContextScope` to route/service layer.
    - Implementation sketch (inside `api/dependencies/context.py`):
       ```python
       async def get_request_context(
             user: AuthenticatedUser = Depends(get_current_user),
             session: AsyncSession = Depends(get_db),
       ) -> ContextScope:
             roles = await userProjectRoleRepository.list_by_user(session, user.id)
             tenant_ids = {role.tenant_id for role in roles}
             assert len(tenant_ids) == 1, "Multi-tenant access not supported yet"
             tenant_id = tenant_ids.pop()
             project_ids = [role.project_id for role in roles]
             await session.execute(text("SELECT set_app_context(:tenant, :projects)"), {
                   "tenant": tenant_id,
                   "projects": project_ids,
             })
             return ContextScope(tenant_id=tenant_id, project_ids=project_ids)
       ```
    - Routers depend on both `get_request_context` and repository methods now require it.

5. **Backfill & Rollout**
   - Management command `python scripts/backfill_tenant_project.py --tenant default --project default` to populate new columns for legacy data if needed.
   - Feature flag `ENFORCE_RLS` to enable policies gradually (set `ALTER TABLE ... FORCE ROW LEVEL SECURITY`).
    - Backfill script responsibilities:
       1. Create default tenant/project rows (id=1) if absent.
       2. Update all existing records setting `tenant_id=1`, `project_id=1`.
       3. Recompute vector store metadata if required (pgvector rows get same tenant/project via update statement).
    - Deploy flow: run migrations → execute backfill script → deploy app with `ENFORCE_RLS=false` → validate → flip flag to true.

6. **Vector Store Alignment**
    - Update `VectorStoreGateway` interface to include `tenant_id`, `project_id` parameters for `upsert_vectors`, `delete_vectors`, `search`.
    - Modify `PgvectorStore` queries to include `WHERE tenant_id = :tenant_id AND project_id = ANY(:project_ids)` once columns exist in embeddings table.
    - Ensure future Milvus collections/partitions utilize the same identifiers so dual-write logic stays symmetrical.

7. **Testing Strategy** *(initial coverage in place; expand to API layer)*
    - Unit tests:
       - `tests/test_multi_tenant_repositories.py` exercises repository filters + RLS context, ensuring cross-tenant reads return empty.
       - TODO: add explicit `ContextScope` helper tests (edge cases, validation).
    - Integration tests (`tests/integration/test_multi_tenant_access.py`) **TBD**:
       1. Seed tenant A/B with projects.
       2. Authenticate as user for tenant A; verify API only returns tenant A data and RLS blocks manual cross-tenant query (expect `psycopg2.errors.InsufficientPrivilege`).
       3. Ensure editing a document preserves tenant/project values.
    - Migration test: run Alembic upgrade/downgrade in CI using temporary database to verify constraints and defaults.

8. **Observability**
   - Add structured logging of `{tenant_id, project_id}` at request start/end (masking where necessary).
   - Metric `unauthorized_access_attempts` increments when RLS blocks a query (capture via exception handler).
    - Dashboards: expose counts of active tenants/projects, top tenants by query volume, and RLS violation rate.

## Expected Outcomes
- All data access paths enforce tenant/project scope.
- Existing functionality works under default tenant/project.
- Foundation ready for intent resolver, conflict workflow, and Milvus partitioning.

## Rollback Plan
- Migrations are reversible: drop FKs/columns and disable RLS.
- Feature flag to disable RLS quickly if misconfiguration blocks traffic.
- Keep backup of pre-migration database snapshot before deployment.

## Task Checklist
- [x] Write Alembic migration `20251003_multi_tenant_core` (up + down) with table creation, column additions, FK/indexes, RLS function/policies.
- [ ] *(Optional)* Document manual backfill guidance for environments that ingest pre-existing data prior to the multi-tenant migration.
- [x] Create `ContextScope` DTO and enforce usage across repositories.
- [x] Add FastAPI `get_request_context` dependency, set session variables, update routers/services.
- [x] Update `VectorStoreGateway` and pgvector implementation to include tenant/project filters.
- [ ] Add unit/integration tests and wire them into CI (pytest markers `multi_tenant`). *(repository-level unit test in place; API/CI wiring outstanding)*
- [ ] Produce developer runbook describing how to onboard a new tenant/project and how to troubleshoot RLS errors.

## Questions for Stakeholders
- Should users ever have access to multiple tenants simultaneously (e.g., MSP scenario)?
- How do we audit role changes (need webhook or event log)?
