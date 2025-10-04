import sys
import uuid
import asyncio
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from infrastructure.database.database import create_tables, drop_tables, get_db, engine
from infrastructure.context import ContextScope
from infrastructure.database.models.documents import UploadedDocument
from infrastructure.database.models.tenancy import Tenant, Project
from infrastructure.database.repositories import DocumentRepository, ChunkRepository, QueryRepository
from infrastructure.database.setup import (
    DEFAULT_PROJECT_SLUG,
    DEFAULT_TENANT_SLUG,
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)


def test_get_db_commits_documents():
    async def workflow() -> None:
        await drop_tables()
        await create_tables()

        async with engine.begin() as conn:
            await configure_multi_tenant_rls(conn)

        await seed_default_tenant_and_project()

        doc_name = f"test_doc_{uuid.uuid4()}.txt"

        db_gen = get_db()
        session = await db_gen.__anext__()
        try:
            tenant_result = await session.execute(
                select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG)
            )
            tenant = tenant_result.scalar_one()

            project_result = await session.execute(
                select(Project).where(Project.slug == DEFAULT_PROJECT_SLUG, Project.tenant_id == tenant.id)
            )
            project = project_result.scalar_one()

            tenant_id = tenant.id
            project_id = project.id

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": tenant_id,
                    "project_ids": str(project_id),
                },
            )

            session.add(
                UploadedDocument(
                    doc_name=doc_name,
                    context="test content",
                    doc_size=len("test content"),
                    doc_type="text/plain",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    created_by_user_id="test-user",
                )
            )
            await session.flush()
        finally:
            try:
                await db_gen.asend(None)
            except StopAsyncIteration:
                pass

        verify_gen = get_db()
        verify_session = await verify_gen.__anext__()
        try:
            await verify_session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": tenant_id,
                    "project_ids": str(project_id),
                },
            )

            result = await verify_session.execute(
                select(UploadedDocument).where(UploadedDocument.doc_name == doc_name)
            )
            saved_doc = result.scalar_one_or_none()
            assert saved_doc is not None

            await verify_session.delete(saved_doc)
        finally:
            try:
                await verify_gen.asend(None)
            except StopAsyncIteration:
                pass

        await engine.dispose()

    asyncio.run(workflow())


def test_sources_retain_history_when_document_deleted():
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
            tenant = tenant_result.scalar_one()

            project_result = await session.execute(
                select(Project).where(
                    Project.slug == DEFAULT_PROJECT_SLUG,
                    Project.tenant_id == tenant.id,
                )
            )
            project = project_result.scalar_one()

            tenant_id = tenant.id
            project_id = project.id
            user_id = "history-tester"

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": tenant_id,
                    "project_ids": str(project_id),
                },
            )

            scope = ContextScope(tenant_id=tenant_id, project_ids=[project_id], user_id=user_id)
            doc_repo = DocumentRepository(session, scope)
            chunk_repo = ChunkRepository(session, scope)
            query_repo = QueryRepository(session, scope)

            doc = await doc_repo.create_document(
                doc_name=f"history_doc_{uuid.uuid4()}.txt",
                context="retain this snippet",
                doc_size=len("retain this snippet"),
                doc_type="text/plain",
            )
            doc_id = doc.id
            doc_name = doc.doc_name
            chunk = await chunk_repo.create_chunk(
                doc_id=doc.id,
                chunk_order=0,
                context_text="contextualized snippet",
                content="retain this snippet",
            )

            query = await query_repo.create_query("history check")
            query_id = query.id
            response = await query_repo.create_response(
                query.id,
                response_text="answer",
                status="success",
            )
            await query_repo.add_source(
                response_id=response.id,
                chunk_id=chunk.id,
                doc_id=doc.id,
                doc_name=doc.doc_name,
                snippet="retain this snippet",
            )
            await session.flush()
            await session.commit()

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": tenant_id,
                    "project_ids": str(project_id),
                },
            )

            deletion_scope = ContextScope(tenant_id=tenant_id, project_ids=[project_id], user_id=user_id)
            deletion_repo = DocumentRepository(session, deletion_scope)
            success = await deletion_repo.delete_document(doc_id)
            assert success is True

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": tenant_id,
                    "project_ids": str(project_id),
                },
            )

            stored_response = await query_repo.get_response_by_query_id(query_id)
            assert stored_response is not None
            sources = await query_repo.get_sources(stored_response.id)
            assert len(sources) == 1
            source = sources[0]
            assert source.chunk_id is None
            assert source.doc_id == doc_id
            assert source.doc_name == doc_name
            assert source.snippet == "retain this snippet"

        finally:
            try:
                await db_gen.asend(None)
            except StopAsyncIteration:
                pass

        await engine.dispose()

    asyncio.run(workflow())
