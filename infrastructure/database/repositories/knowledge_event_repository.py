from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.knowledge import KnowledgeEvent

from pgvector.sqlalchemy import Vector
from sqlalchemy import func

class KnowledgeEventRepository:
    """Repository helpers for temporal knowledge events."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_event(
        self,
        *,
        chunk_id: Optional[int],
        statement_id: Optional[UUID],
        statement_text: str,
        triplets: list,
        statement_type: str,
        temporal_type: str,
        valid_at,
        invalid_at,
        embedding: Optional[list] = None,
    ) -> KnowledgeEvent:
        event = KnowledgeEvent(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            chunk_id=chunk_id,
            statement_id=statement_id,
            statement=statement_text,
            triplets=triplets,
            statement_type=statement_type,
            temporal_type=temporal_type,
            valid_at=valid_at,
            invalid_at=invalid_at,
            embedding=embedding,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def update_invalidation(
        self,
        event_id: UUID,
        *,
        invalid_at,
        invalidated_by: Optional[UUID],
        expired_at=None,
    ) -> bool:
        stmt = select(KnowledgeEvent).where(
            KnowledgeEvent.id == event_id,
            KnowledgeEvent.tenant_id == self.context.tenant_id,
            KnowledgeEvent.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return False
        record.invalid_at = invalid_at
        if expired_at is not None:
            record.invalidated_by = invalidated_by
            record.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[KnowledgeEvent]:
        """Return top-k events by cosine similarity to the query embedding."""
        stmt = (
            select(KnowledgeEvent)
            .where(
                KnowledgeEvent.tenant_id == self.context.tenant_id,
                KnowledgeEvent.project_id.in_(self.context.project_ids),
                KnowledgeEvent.embedding.isnot(None),
            )
            .order_by(KnowledgeEvent.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_events_for_statement_ids(
        self, statement_ids: Sequence[UUID]
    ) -> List[KnowledgeEvent]:
        ids = {sid for sid in statement_ids if sid}
        if not ids:
            return []
        stmt = select(KnowledgeEvent).where(
            KnowledgeEvent.statement_id.in_(ids),
            KnowledgeEvent.tenant_id == self.context.tenant_id,
            KnowledgeEvent.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
