from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.knowledge import KnowledgeEvent, KnowledgeStatement
from datetime import datetime, timezone

class KnowledgeEventRepository:
    """Repository helpers for temporal knowledge events."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_event(
        self,
        *,
        chunk_id: Optional[int],
        statement_id: UUID,
        triplets: list,
        valid_at,
        invalid_at,
        invalidated_by: Optional[UUID] = None,
    ) -> KnowledgeEvent:
        event = KnowledgeEvent(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            chunk_id=chunk_id,
            statement_id=statement_id,
            triplets=triplets,
            valid_at=valid_at,
            invalid_at=invalid_at,
            invalidated_by=invalidated_by,
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
        record.invalidated_by = invalidated_by
        if expired_at is not None:
            record.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[KnowledgeEvent]:
        """Return top-k events by cosine similarity to the statement embedding."""
        stmt = (
            select(KnowledgeEvent)
            .join(KnowledgeStatement, KnowledgeEvent.statement_id == KnowledgeStatement.id)
            .where(
                KnowledgeEvent.tenant_id == self.context.tenant_id,
                KnowledgeEvent.project_id.in_(self.context.project_ids),
                KnowledgeStatement.tenant_id == self.context.tenant_id,
                KnowledgeStatement.project_id.in_(self.context.project_ids),
                KnowledgeStatement.embedding.isnot(None),
            )
            .order_by(KnowledgeStatement.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_events_by_triplet_ids(self, triplet_ids: Sequence[str]) -> list[KnowledgeEvent]:
        """Fetch events whose stored triplet UUIDs intersect the provided list."""
        if not triplet_ids:
            return []
        # Stored as JSON array on knowledge_events.triplets; cast to JSONB for contains.
        contains_clauses = [KnowledgeEvent.triplets.cast(JSONB).contains([tid]) for tid in triplet_ids]
        stmt = select(KnowledgeEvent).where(
            KnowledgeEvent.tenant_id == self.context.tenant_id,
            KnowledgeEvent.project_id.in_(self.context.project_ids),
            KnowledgeEvent.triplets.isnot(None),
            or_(*contains_clauses),
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

    async def get_event_by_id(self, event_id: UUID) -> Optional[KnowledgeEvent]:
        stmt = select(KnowledgeEvent).where(
            KnowledgeEvent.id == event_id,
            KnowledgeEvent.tenant_id == self.context.tenant_id,
            KnowledgeEvent.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
