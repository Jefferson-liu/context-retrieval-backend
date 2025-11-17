import sys
import asyncio
import uuid
import math
from pathlib import Path

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from infrastructure.context import ContextScope
from infrastructure.database.database import create_tables, engine, get_db
from infrastructure.database.models.tenancy import Project, Tenant
from infrastructure.database.repositories import DocumentRepository, ChunkRepository
from infrastructure.database.setup import (
    DEFAULT_PROJECT_SLUG,
    DEFAULT_TENANT_SLUG,
    DEFAULT_USER_ID,
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)
from infrastructure.vector_store import PgVectorStore, VectorRecord


def test_pgvector_store_respects_scope():
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

            vector_store = PgVectorStore(session)
            default_doc_repo = DocumentRepository(session, default_scope)
            default_chunk_repo = ChunkRepository(session, default_scope)

            default_doc = await default_doc_repo.create_document(
                doc_name=f"default-{uuid.uuid4()}.txt",
                context="default tenant content",
                doc_size=25,
                doc_type="text/plain",
            )
            default_chunk = await default_chunk_repo.create_chunk(
                default_doc.id,
                0,
                "contextualized",
                "raw",
            )

            def generate_vector(seed: float) -> list[float]:
                return [math.sin(seed + idx) for idx in range(settings.EMBEDDING_VECTOR_DIM)]

            default_embedding = generate_vector(0.1)
            await vector_store.upsert_vectors(
                [
                    VectorRecord(
                        chunk_id=default_chunk.id,
                        embedding=default_embedding,
                        tenant_id=default_scope.tenant_id,
                        project_id=default_chunk.project_id,
                    )
                ]
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
            other_doc_repo = DocumentRepository(session, other_scope)
            other_chunk_repo = ChunkRepository(session, other_scope)

            other_doc = await other_doc_repo.create_document(
                doc_name=f"other-{uuid.uuid4()}.txt",
                context="other tenant content",
                doc_size=22,
                doc_type="text/plain",
            )
            other_chunk = await other_chunk_repo.create_chunk(
                other_doc.id,
                0,
                "contextualized",
                "raw",
            )

            other_embedding = generate_vector(1.3)
            await vector_store.upsert_vectors(
                [
                    VectorRecord(
                        chunk_id=other_chunk.id,
                        embedding=other_embedding,
                        tenant_id=other_scope.tenant_id,
                        project_id=other_chunk.project_id,
                    )
                ]
            )

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": default_tenant.id,
                    "project_ids": str(default_project.id),
                },
            )

            results = await vector_store.search(
                default_embedding,
                tenant_id=default_scope.tenant_id,
                project_ids=default_scope.project_ids,
                user_id=default_scope.user_id,
                top_k=5,
            )

            assert len(results) == 1
            assert results[0].chunk_id == default_chunk.id
            assert results[0].doc_id == default_doc.id

        finally:
            try:
                await db_gen.asend(None)
            except StopAsyncIteration:
                pass

        await engine.dispose()

    asyncio.run(workflow())
