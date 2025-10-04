from __future__ import annotations

from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.documents import Chunk, Embedding, Document
from schemas.responses.vector_search_result import VectorSearchResult

from .gateway import VectorRecord, VectorStoreGateway


class PgVectorStore(VectorStoreGateway):
    """Vector store backed by the existing pgvector-powered embeddings table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_vectors(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return

        values = [
            {
                "chunk_id": record.chunk_id,
                "embedding": list(record.embedding),
                "tenant_id": record.tenant_id,
                "project_id": record.project_id,
            }
            for record in records
        ]

        stmt = pg_insert(Embedding).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Embedding.chunk_id],
            set_={
                "embedding": stmt.excluded.embedding,
                "tenant_id": stmt.excluded.tenant_id,
                "project_id": stmt.excluded.project_id,
            },
        )

        await self.db.execute(stmt)

    async def delete_vectors(
        self,
        chunk_ids: Sequence[int],
        *,
        tenant_id: int,
        project_id: int | None = None,
    ) -> None:
        if not chunk_ids:
            return

        stmt = delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids))
        stmt = stmt.where(Embedding.tenant_id == tenant_id)
        if project_id is not None:
            stmt = stmt.where(Embedding.project_id == project_id)

        await self.db.execute(stmt)

    async def search(
        self,
        query_embedding: Sequence[float],
        *,
        tenant_id: int,
        project_ids: Sequence[int],
        top_k: int = 10,
    ) -> Sequence[VectorSearchResult]:
        stmt = (
            select(
                Chunk.id,
                Chunk.context,
                Chunk.content,
                Chunk.doc_id,
                Document.doc_name,
                (1 - Embedding.embedding.cosine_distance(query_embedding)).label("similarity_score"),
            )
            .join(Embedding, Chunk.id == Embedding.chunk_id)
            .join(Document, Chunk.doc_id == Document.id)
            .where(
                Embedding.embedding.isnot(None),
                Chunk.tenant_id == tenant_id,
                Chunk.project_id.in_(project_ids),
            )
            .order_by(Embedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            VectorSearchResult(
                chunk_id=row[0],
                context=row[1],
                content=row[2],
                doc_id=row[3],
                doc_name=row[4],
                similarity_score=row[5],
            )
            for row in rows
        ]
