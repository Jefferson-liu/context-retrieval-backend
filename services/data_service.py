from __future__ import annotations

import logging
from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.repositories import DataRepository, ChunkRepository
from services.chunking import chunk_document

logger = logging.getLogger(__name__)


class DataService:
    """Service to create/list/delete data records and associated chunks."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data_repo = DataRepository(session)
        self.chunk_repo = ChunkRepository(session)

    async def create_record(self, *, title: str, body: str, chunking: bool = True) -> dict:
        chunks = chunk_document(body, chunk_size=1000) if chunking else [body]
        if not chunks:
            chunks = [body]
        record = await self.data_repo.create_with_chunks(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            title=title,
            body=body,
            chunks=chunks,
        )
        return {"id": record.id, "title": record.title, "body": record.body, "chunk_count": len(chunks)}

    async def create_records_bulk(
        self,
        files: list[tuple[str, str]],
        *,
        chunking: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        """Ingest many records with per-file transaction boundaries."""
        successes: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for idx, (title, body) in enumerate(files):
            try:
                record = await self.create_record(title=title, body=body, chunking=chunking)
                await self.session.commit()
                successes.append(record)
            except Exception as exc:
                await self.session.rollback()
                errors.append({"index": idx, "title": title, "error": str(exc)})

        return {"successes": successes, "errors": errors}

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
        record = await self.data_repo.get(data_id, tenant_id=self.tenant_id, user_id=self.user_id)
        if record is None:
            return False
        return await self.data_repo.delete(data_id, tenant_id=self.tenant_id, user_id=self.user_id)
