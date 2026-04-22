from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoEmbeddingRecord, RepoFileSnapshotRecord, RepoSubjectRecord

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - environment specific
    Vector = None


class RepoEmbeddingRepository:
    """Persistence and query operations for repository embedding vectors."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_many(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        insert_stmt = postgres_insert(RepoEmbeddingRecord).values(rows)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["embedding_run_id", "subject_id", "kind"],
            set_={
                "source_run_id": insert_stmt.excluded.source_run_id,
                "source_file_summary_run_id": insert_stmt.excluded.source_file_summary_run_id,
                "text_for_embedding": insert_stmt.excluded.text_for_embedding,
                "text_hash": insert_stmt.excluded.text_hash,
                "embedding": insert_stmt.excluded.embedding,
                "embedding_dims": insert_stmt.excluded.embedding_dims,
            },
        ).returning(RepoEmbeddingRecord.subject_id)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def list_for_embedding_run(
        self,
        *,
        embedding_run_id: str,
        source_run_id: str,
        limit: int,
        offset: int,
        kind: str | None,
        language: str | None,
        subject_path_prefix: str | None,
    ) -> list[tuple[RepoEmbeddingRecord, RepoSubjectRecord, RepoFileSnapshotRecord | None]]:
        stmt = (
            select(RepoEmbeddingRecord, RepoSubjectRecord, RepoFileSnapshotRecord)
            .join(RepoSubjectRecord, RepoEmbeddingRecord.subject_id == RepoSubjectRecord.id)
            .outerjoin(
                RepoFileSnapshotRecord,
                (RepoFileSnapshotRecord.run_id == source_run_id)
                & (RepoFileSnapshotRecord.subject_id == RepoEmbeddingRecord.subject_id),
            )
            .where(RepoEmbeddingRecord.embedding_run_id == embedding_run_id)
            .order_by(RepoSubjectRecord.subject_path)
            .offset(offset)
            .limit(limit)
        )
        if kind:
            stmt = stmt.where(RepoEmbeddingRecord.kind == kind)
        if language:
            stmt = stmt.where(RepoSubjectRecord.language == language)
        if subject_path_prefix:
            stmt = stmt.where(RepoSubjectRecord.subject_path.like(f"{subject_path_prefix}%"))

        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def search_similar(
        self,
        *,
        embedding_run_id: str,
        kind: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[dict]:
        if Vector is None:
            raise RuntimeError("pgvector is required for vector similarity search")

        distance = RepoEmbeddingRecord.embedding.cosine_distance(query_embedding)
        similarity = (1 - distance).label("similarity")

        stmt = (
            select(RepoEmbeddingRecord.subject_id, similarity)
            .where(
                RepoEmbeddingRecord.embedding_run_id == embedding_run_id,
                RepoEmbeddingRecord.kind == kind,
            )
            .order_by(distance)
            .limit(limit)
        )
        result = await self.session.execute(stmt)

        payload: list[dict] = []
        for row in result.all():
            payload.append(
                {
                    "subject_id": row.subject_id,
                    "similarity": float(row.similarity),
                }
            )
        return payload
