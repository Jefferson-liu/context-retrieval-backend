from __future__ import annotations

from datetime import datetime
import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.repositories import DataRepository, ChunkRepository
from services.chunking import chunk_document
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.utils.bulk_utils import RawEpisode
from infrastructure.graphiti import (
    DEFAULT_ENTITY_TYPES,
    DEFAULT_EDGE_TYPE_MAP,
    DEFAULT_EDGE_TYPES,
    build_group_id,
)

logger = logging.getLogger(__name__)


class DataService:
    """Service to create/list/delete data records and associated chunks."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
        graphiti_client: Graphiti | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data_repo = DataRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.graphiti_client = graphiti_client

    async def create_record(self, *, title: str, body: str) -> dict:
        chunks = chunk_document(body)
        record = await self.data_repo.create_with_chunks(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            title=title,
            body=body,
            chunks=chunks,
        )
        if self.graphiti_client:
            episodes: list[RawEpisode] = [
                RawEpisode(
                    name=f"data-{record.id}-chunk-{i}",
                    content=chunk,
                    source_description="data_chunk",
                    source=EpisodeType.text,
                    reference_time=datetime.now(),
                    entity_types=DEFAULT_ENTITY_TYPES,
                    edge_types=DEFAULT_EDGE_TYPES,
                    edge_type_map=DEFAULT_EDGE_TYPE_MAP,
                )
                for i, chunk in enumerate(chunks)
            ]
            try:
                await self.graphiti_client.add_episode_bulk(episodes, group_id=build_group_id(self.tenant_id, self.user_id))
            except Exception as exc:
                logger.warning("Graphiti bulk ingestion failed for data-%s: %s", record.id, exc)
                raise
        return {"id": record.id, "title": record.title, "body": record.body, "chunk_count": len(chunks)}

    async def list_records(self) -> List[dict]:
        records = await self.data_repo.list(tenant_id=self.tenant_id, user_id=self.user_id)
        return [{"id": r.id, "title": r.title, "body": r.body} for r in records]

    async def get_record(self, data_id: int) -> dict | None:
        record = await self.data_repo.get(data_id, tenant_id=self.tenant_id, user_id=self.user_id)
        if not record:
            return None
        chunks = await self.chunk_repo.list_for_data(data_id, tenant_id=self.tenant_id, user_id=self.user_id)
        return {
            "id": record.id,
            "title": record.title,
            "body": record.body,
            "chunks": [{"id": c.id, "index": c.chunk_index, "content": c.content} for c in chunks],
        }

    async def delete_record(self, data_id: int) -> bool:
        return await self.data_repo.delete(data_id, tenant_id=self.tenant_id, user_id=self.user_id)
