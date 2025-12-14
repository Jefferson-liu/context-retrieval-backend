from __future__ import annotations

from typing import Iterable, List, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import DataRecord, ChunkRecord


class DataRepository:
    """Persistence layer for data records and their chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_with_chunks(
        self,
        *,
        title: str,
        body: str,
        chunks: Sequence[str],
    ) -> DataRecord:
        record = DataRecord(title=title, body=body)
        self.session.add(record)
        await self.session.flush()

        for idx, content in enumerate(chunks):
            self.session.add(
                ChunkRecord(
                    data_id=record.id,
                    chunk_index=idx,
                    content=content,
                )
            )
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def list(self) -> List[DataRecord]:
        stmt = select(DataRecord).order_by(DataRecord.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, data_id: int) -> DataRecord | None:
        stmt = select(DataRecord).where(DataRecord.id == data_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, data_id: int) -> bool:
        stmt = delete(DataRecord).where(DataRecord.id == data_id)
        result = await self.session.execute(stmt)
        # rows_deleted can be None on some dialects; treat truthy as success
        return bool(result.rowcount)
