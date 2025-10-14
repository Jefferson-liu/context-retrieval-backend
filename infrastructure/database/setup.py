from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from infrastructure.database.database import SessionLocal
from infrastructure.database.models.tenancy import Tenant, Project, UserProjectRole

DEFAULT_TENANT_SLUG = "default"
DEFAULT_PROJECT_SLUG = "default"
DEFAULT_TENANT_NAME = "Default Tenant"
DEFAULT_PROJECT_NAME = "Default Project"
DEFAULT_USER_ID = "demo-user"
DEFAULT_USER_ROLE = "admin"


async def configure_multi_tenant_rls(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION set_app_context(p_tenant integer, p_projects text)
            RETURNS void AS $$
            BEGIN
                PERFORM set_config('app.current_tenant', coalesce(p_tenant::text, ''), true);
                PERFORM set_config('app.current_projects', coalesce(p_projects, ''), true);
            END;
            $$ LANGUAGE plpgsql SECURITY DEFINER;
            """
        )
    )

    tables = [
        "uploaded_documents",
        "chunks",
        "embeddings",
        "queries",
        "responses",
        "sources",
        "knowledge_entities",
        "knowledge_relationships",
        "knowledge_relationship_metadata",
    ]

    for table in tables:
        await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(
            text(
                f"DROP POLICY IF EXISTS {table}_tenant_project_rls ON {table}"
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE POLICY {table}_tenant_project_rls
                ON {table}
                USING (
                    current_setting('app.current_tenant', true) <> ''
                    AND {table}.tenant_id = current_setting('app.current_tenant')::integer
                    AND (
                        current_setting('app.current_projects', true) = ''
                        OR {table}.project_id = ANY(string_to_array(current_setting('app.current_projects'), ',')::integer[])
                    )
                )
                WITH CHECK (
                    current_setting('app.current_tenant', true) <> ''
                    AND {table}.tenant_id = current_setting('app.current_tenant')::integer
                    AND (
                        current_setting('app.current_projects', true) = ''
                        OR {table}.project_id = ANY(string_to_array(current_setting('app.current_projects'), ',')::integer[])
                    )
                )
                """
            )
        )


async def seed_default_tenant_and_project() -> None:
    async with SessionLocal() as session:
        tenant = await _get_or_create_tenant(session)
        project = await _get_or_create_project(session, tenant.id)
        await _ensure_default_user_role(session, tenant.id, project.id)
        await session.commit()


async def _get_or_create_tenant(session: AsyncSession) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG))
    tenant = result.scalar_one_or_none()
    if tenant:
        return tenant

    tenant = Tenant(name=DEFAULT_TENANT_NAME, slug=DEFAULT_TENANT_SLUG)
    session.add(tenant)
    await session.flush()
    return tenant


async def _get_or_create_project(session: AsyncSession, tenant_id: int) -> Project:
    result = await session.execute(
        select(Project).where(
            Project.tenant_id == tenant_id,
            Project.slug == DEFAULT_PROJECT_SLUG,
        )
    )
    project = result.scalar_one_or_none()
    if project:
        return project

    project = Project(
        tenant_id=tenant_id,
        name=DEFAULT_PROJECT_NAME,
        slug=DEFAULT_PROJECT_SLUG,
    )
    session.add(project)
    await session.flush()
    return project


async def _ensure_default_user_role(session: AsyncSession, tenant_id: int, project_id: int) -> None:
    result = await session.execute(
        select(UserProjectRole).where(
            UserProjectRole.user_id == DEFAULT_USER_ID,
            UserProjectRole.project_id == project_id,
        )
    )
    role = result.scalar_one_or_none()
    if role:
        return

    session.add(
        UserProjectRole(
            user_id=DEFAULT_USER_ID,
            tenant_id=tenant_id,
            project_id=project_id,
            role=DEFAULT_USER_ROLE,
        )
    )