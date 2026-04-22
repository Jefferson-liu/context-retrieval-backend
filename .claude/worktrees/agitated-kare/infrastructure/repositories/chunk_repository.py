from __future__ import annotations

from typing import List, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import ChunkRecord, DataRecord


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

    async def list_for_data(self, data_id: int, *, tenant_id: str, user_id: str | None = None) -> List[ChunkRecord]:
        stmt = (
            select(ChunkRecord)
            .join(DataRecord, ChunkRecord.data_id == DataRecord.id)
            .where(ChunkRecord.data_id == data_id, DataRecord.tenant_id == tenant_id)
            .order_by(ChunkRecord.chunk_index)
        )
        if user_id:
            stmt = stmt.where(DataRecord.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_data(self, data_id: int, *, tenant_id: str, user_id: str | None = None) -> int:
        # ensure scoping through parent
        parent_stmt = select(DataRecord.id).where(DataRecord.id == data_id, DataRecord.tenant_id == tenant_id)
        if user_id:
            parent_stmt = parent_stmt.where(DataRecord.user_id == user_id)
        parent_result = await self.session.execute(parent_stmt)
        parent = parent_result.scalar_one_or_none()
        if not parent:
            return 0

        stmt = delete(ChunkRecord).where(ChunkRecord.data_id == data_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0
