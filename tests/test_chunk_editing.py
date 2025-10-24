import asyncio
import sys
from pathlib import Path

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from infrastructure.context import ContextScope
from infrastructure.database.database import create_tables, engine, get_db
from infrastructure.database.models.tenancy import Project, Tenant
from infrastructure.database.repositories import ChunkRepository, DocumentRepository
from infrastructure.database.setup import (
    DEFAULT_PROJECT_SLUG,
    DEFAULT_TENANT_SLUG,
    DEFAULT_USER_ID,
    configure_multi_tenant_rls,
    seed_default_tenant_and_project,
)
from infrastructure.vector_store import create_vector_store, VectorRecord
from services.document.chunk_editing import ChunkEditingService


class FakeEmbedder:
    def __init__(self) -> None:
        self.contextualize_calls: list[tuple[str, str]] = []
        self.generate_calls: list[str] = []

    async def contextualize_chunk_content(self, chunk_content: str, full_content: str) -> str:
        self.contextualize_calls.append((chunk_content, full_content))
        return f"context::{chunk_content}"

    async def generate_embedding(self, text: str) -> list[float]:
        self.generate_calls.append(text)
        multiplier = float(len(self.generate_calls))
        return [multiplier] * settings.EMBEDDING_VECTOR_DIM


def test_chunk_editing_updates_chunk_and_embedding():
    async def workflow() -> None:
        await create_tables()

        async with engine.begin() as conn:
            for table in (
                "sources",
                "responses",
                "queries",
                "embeddings",
                "chunks",
                "documents",
            ):
                await conn.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
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

            await session.execute(
                text("SELECT set_app_context(:tenant_id, :project_ids)"),
                {
                    "tenant_id": tenant.id,
                    "project_ids": str(project.id),
                },
            )

            scope = ContextScope(
                tenant_id=tenant.id,
                project_ids=[project.id],
                user_id=DEFAULT_USER_ID,
            )

            doc_repo = DocumentRepository(session, scope)
            chunk_repo = ChunkRepository(session, scope)
            vector_store = create_vector_store(session)

            document_body = "prefix original content suffix"
            document = await doc_repo.create_document(
                doc_name="sample.txt",
                content=document_body,
                doc_size=len(document_body),
                doc_type="text/plain",
            )

            chunk = await chunk_repo.create_chunk(
                document.id,
                0,
                "original context",
                "original content",
            )

            await vector_store.upsert_vectors(
                [
                    VectorRecord(
                        chunk_id=chunk.id,
                        embedding=[0.0] * settings.EMBEDDING_VECTOR_DIM,
                        tenant_id=scope.tenant_id,
                        project_id=chunk.project_id,
                    )
                ]
            )
            await session.flush()

            embedder = FakeEmbedder()
            service = ChunkEditingService(
                session,
                scope,
                embedder=embedder,
                vector_store=vector_store,
            )

            updated_chunk = await service.update_chunk(
                chunk.id,
                content="updated content",
            )

            assert updated_chunk is not None
            assert updated_chunk.content == "updated content"
            assert updated_chunk.context == "context::updated content"

            expected_manual_body = document_body.replace("original content", "updated content", 1)
            assert embedder.contextualize_calls == [("updated content", expected_manual_body)]
            assert embedder.generate_calls[-1] == "context::updated content updated content"

            await session.refresh(document)
            assert document.content == expected_manual_body
            assert document.context == expected_manual_body
            assert document.doc_size == len(expected_manual_body)

            embedding_row = await chunk_repo.get_embedding_by_chunk_id(chunk.id)
            assert embedding_row is not None
            stored_values = list(embedding_row.embedding)
            assert all(value == 1.0 for value in stored_values[:3]), stored_values[:3]

            updated_chunk = await service.update_chunk(
                chunk.id,
                content="second content",
            )

            assert updated_chunk is not None
            await session.refresh(document)
            expected_second_body = expected_manual_body.replace("updated content", "second content", 1)
            assert embedder.contextualize_calls == [
                ("updated content", expected_manual_body),
                ("second content", expected_second_body),
            ]
            assert embedder.generate_calls[-1] == "context::second content second content"

            assert document.content == expected_second_body
            assert document.context == expected_second_body
            assert document.doc_size == len(expected_second_body)

            embedding_row = await chunk_repo.get_embedding_by_chunk_id(chunk.id)
            assert embedding_row is not None
            stored_values = list(embedding_row.embedding)
            assert all(value == 2.0 for value in stored_values[:3]), stored_values[:3]

        finally:
            try:
                await db_gen.asend(None)
            except StopAsyncIteration:
                pass

        await engine.dispose()

    asyncio.run(workflow())
