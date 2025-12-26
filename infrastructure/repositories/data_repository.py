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
        tenant_id: str,
        user_id: str,
        title: str,
        body: str,
        chunks: Sequence[str],
    ) -> DataRecord:
        record = DataRecord(tenant_id=tenant_id, user_id=user_id, title=title, body=body)
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

    async def list(self, *, tenant_id: str, user_id: str | None = None) -> List[DataRecord]:
        stmt = select(DataRecord).where(DataRecord.tenant_id == tenant_id).order_by(DataRecord.id)
        if user_id:
            stmt = stmt.where(DataRecord.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, data_id: int, *, tenant_id: str, user_id: str | None = None) -> DataRecord | None:
        stmt = select(DataRecord).where(DataRecord.id == data_id, DataRecord.tenant_id == tenant_id)
        if user_id:
            stmt = stmt.where(DataRecord.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, data_id: int, *, tenant_id: str, user_id: str | None = None) -> bool:
        stmt = delete(DataRecord).where(DataRecord.id == data_id, DataRecord.tenant_id == tenant_id)
        if user_id:
            stmt = stmt.where(DataRecord.user_id == user_id)
        result = await self.session.execute(stmt)
        # rows_deleted can be None on some dialects; treat truthy as success
        return bool(result.rowcount)
