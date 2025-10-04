import sys
import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.context import ContextScope
from infrastructure.database.database import create_tables, engine, get_db
from infrastructure.database.models.documents import UploadedDocument
from infrastructure.database.models.tenancy import Project, Tenant
from infrastructure.database.repositories import DocumentRepository
from infrastructure.database.setup import (
    DEFAULT_PROJECT_SLUG,
    DEFAULT_TENANT_SLUG,
    DEFAULT_USER_ID,
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)


def test_document_repository_isolates_tenants():
    async def workflow() -> None:
        await create_tables()

        async with engine.begin() as conn:
            for table_name in (
                "sources",
                "responses",
                "queries",
                "embeddings",
                "chunks",
                "uploaded_documents",
            ):
                await conn.execute(text(f"TRUNCATE {table_name} RESTART IDENTITY CASCADE"))

            await configure_multi_tenant_rls(conn)

        await seed_default_tenant_and_project()

        db_gen = get_db()
        session = await db_gen.__anext__()
        try:
            tenant_result = await session.execute(
                select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG)
            )
            default_tenant = tenant_result.scalar_one()

            project_result = await session.execute(
                select(Project).where(
                    Project.slug == DEFAULT_PROJECT_SLUG,
                    Project.tenant_id == default_tenant.id,
                )
            )
            default_project = project_result.scalar_one()

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": default_tenant.id,
                    "project_ids": str(default_project.id),
                },
            )

            default_scope = ContextScope(
                tenant_id=default_tenant.id,
                project_ids=[default_project.id],
                user_id=DEFAULT_USER_ID,
            )
            default_repo = DocumentRepository(session, default_scope)
            default_doc = await default_repo.create_document(
                doc_name=f"default-{uuid.uuid4()}.txt",
                context="default tenant content",
                doc_size=25,
                doc_type="text/plain",
            )

            other_tenant = Tenant(
                name=f"tenant-{uuid.uuid4()}",
                slug=f"tenant-{uuid.uuid4()}",
            )
            session.add(other_tenant)
            await session.flush()

            other_project = Project(
                tenant_id=other_tenant.id,
                name=f"project-{uuid.uuid4()}",
                slug=f"project-{uuid.uuid4()}",
            )
            session.add(other_project)
            await session.flush()

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": other_tenant.id,
                    "project_ids": str(other_project.id),
                },
            )

            other_scope = ContextScope(
                tenant_id=other_tenant.id,
                project_ids=[other_project.id],
                user_id="other-user",
            )
            other_repo = DocumentRepository(session, other_scope)
            other_doc = await other_repo.create_document(
                doc_name=f"other-{uuid.uuid4()}.txt",
                context="other tenant content",
                doc_size=22,
                doc_type="text/plain",
            )

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": default_tenant.id,
                    "project_ids": str(default_project.id),
                },
            )

            docs = await default_repo.get_all_documents()
            assert {doc.id for doc in docs} == {default_doc.id}

            lookup = await default_repo.get_document_by_id(other_doc.id)
            assert lookup is None

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": other_tenant.id,
                    "project_ids": str(other_project.id),
                },
            )
            cross_check = await other_repo.get_document_by_id(default_doc.id)
            assert cross_check is None

        finally:
            try:
                await db_gen.asend(None)
            except StopAsyncIteration:
                pass

        await engine.dispose()

    asyncio.run(workflow())
