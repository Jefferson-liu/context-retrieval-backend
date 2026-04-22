from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import DataRecord, GraphitiEpisodeRecord


class GraphitiEpisodeRepository:
    """Persistence layer for Graphiti episode mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(self, *, data_id: int, episode_uuids: Sequence[str]) -> None:
        """Store episode UUID mappings for a data record."""
        unique_uuids = {uuid for uuid in episode_uuids if uuid}
        for episode_uuid in unique_uuids:
            self.session.add(GraphitiEpisodeRecord(data_id=data_id, episode_uuid=episode_uuid))
        await self.session.flush()

    async def list_episode_uuids_for_data(
        self, data_id: int, *, tenant_id: str, user_id: str | None = None
    ) -> list[str]:
        """Return scoped episode UUID mappings for a data record."""
        stmt = (
            select(GraphitiEpisodeRecord.episode_uuid)
            .join(DataRecord, GraphitiEpisodeRecord.data_id == DataRecord.id)
            .where(GraphitiEpisodeRecord.data_id == data_id, DataRecord.tenant_id == tenant_id)
            .order_by(GraphitiEpisodeRecord.id)
        )
        if user_id:
            stmt = stmt.where(DataRecord.user_id == user_id)

        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def delete_for_data(self, data_id: int, *, tenant_id: str, user_id: str | None = None) -> int:
        """Delete scoped episode mappings for a data record."""
        parent_stmt = select(DataRecord.id).where(DataRecord.id == data_id, DataRecord.tenant_id == tenant_id)
        if user_id:
            parent_stmt = parent_stmt.where(DataRecord.user_id == user_id)
        parent_result = await self.session.execute(parent_stmt)
        parent = parent_result.scalar_one_or_none()
        if not parent:
            return 0

        stmt = delete(GraphitiEpisodeRecord).where(GraphitiEpisodeRecord.data_id == data_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0
