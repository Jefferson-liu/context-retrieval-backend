from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFileChunkRecord


class RepoChunkRepository:
    """Persistence for run-scoped repository file chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_subject(self, *, run_id: str, subject_id: str, chunks: list[str]) -> int:
        await self.session.execute(
            delete(RepoFileChunkRecord).where(
                RepoFileChunkRecord.run_id == run_id,
                RepoFileChunkRecord.subject_id == subject_id,
            )
        )
        for idx, content in enumerate(chunks):
            self.session.add(
                RepoFileChunkRecord(
                    id=str(uuid4()),
                    run_id=run_id,
                    subject_id=subject_id,
                    chunk_index=idx,
                    content=content,
                    content_hash=sha256(content.encode("utf-8")).hexdigest(),
                    char_start=None,
                    char_end=None,
                )
            )
        await self.session.flush()
        return len(chunks)

    async def list_for_subject(self, *, run_id: str, subject_id: str) -> list[RepoFileChunkRecord]:
        stmt = (
            select(RepoFileChunkRecord)
            .where(
                RepoFileChunkRecord.run_id == run_id,
                RepoFileChunkRecord.subject_id == subject_id,
            )
            .order_by(RepoFileChunkRecord.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
