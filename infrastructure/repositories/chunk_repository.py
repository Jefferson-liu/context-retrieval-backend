from __future__ import annotations

from typing import List, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import ChunkRecord


class ChunkRepository:
    """Persistence layer for chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(
        self,
        *,
        data_id: int,
        contents: Sequence[str],
    ) -> List[ChunkRecord]:
        chunks: List[ChunkRecord] = []
        for idx, content in enumerate(contents):
            chunk = ChunkRecord(data_id=data_id, chunk_index=idx, content=content)
            self.session.add(chunk)
            chunks.append(chunk)
        await self.session.flush()
        return chunks

    async def list_for_data(self, data_id: int) -> List[ChunkRecord]:
        stmt = (
            select(ChunkRecord)
            .where(ChunkRecord.data_id == data_id)
            .order_by(ChunkRecord.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_data(self, data_id: int) -> int:
        stmt = delete(ChunkRecord).where(ChunkRecord.data_id == data_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0
