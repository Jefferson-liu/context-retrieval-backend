from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.knowledge import (
    KnowledgeStatement,
    KnowledgeStatementTriplet,
    KnowledgeStatementInvalidation,
    KnowledgeEvent,
    KnowledgeEventInvalidation,
    KnowledgeEventInvalidationBatch,
    KnowledgeEventInvalidationBatchItem,
)


class KnowledgeStatementRepository:
    """Repository helpers for temporal knowledge statements."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_statement(
        self,
        *,
        document_id: Optional[int],
        chunk_id: Optional[int],
        statement_text: str,
        statement_type: str,
        temporal_type: str,
        valid_at,
        invalid_at,
        embedding=None,
    ) -> KnowledgeStatement:
        statement = KnowledgeStatement(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            document_id=document_id,
            chunk_id=chunk_id,
            statement=statement_text,
            statement_type=statement_type,
            temporal_type=temporal_type,
            valid_at=valid_at,
            invalid_at=invalid_at,
            embedding=embedding,
        )
        self.db.add(statement)
        await self.db.flush()
        return statement

    async def delete_statements_for_document(self, document_id: int) -> int:
        stmt = select(KnowledgeStatement).where(
            KnowledgeStatement.document_id == document_id,
            KnowledgeStatement.tenant_id == self.context.tenant_id,
            KnowledgeStatement.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        statements = result.scalars().all()
        for statement in statements:
            await self.db.delete(statement)
        count = len(statements)
        if count:
            await self.db.flush()
        return count

    async def list_statements_by_ids(
        self,
        statement_ids: Sequence[str],
    ) -> Dict[str, KnowledgeStatement]:
        unique_ids = {statement_id for statement_id in statement_ids if statement_id}
        if not unique_ids:
            return {}

        stmt = select(KnowledgeStatement).where(
            KnowledgeStatement.id.in_(unique_ids),
            KnowledgeStatement.tenant_id == self.context.tenant_id,
            KnowledgeStatement.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return {str(row.id): row for row in rows}


    async def get_statement_by_id(
        self,
        statement_id: str,
    ) -> Optional[KnowledgeStatement]:
        stmt = select(KnowledgeStatement).where(
            KnowledgeStatement.id == statement_id,
            KnowledgeStatement.tenant_id == self.context.tenant_id,
            KnowledgeStatement.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_invalid_at(
        self,
        statement_id: str,
        *,
        invalid_at: datetime,
    ) -> bool:
        record = await self.get_statement_by_id(statement_id)
        if not record:
            return False
        current = record.invalid_at
        if current and current <= invalid_at:
            return False
        record.invalid_at = invalid_at
        await self.db.flush()
        return True


class KnowledgeStatementTripletRepository:
    """Repository helpers for statement-level triplets."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_triplet(
        self,
        *,
        statement_id,
        subject_entity_id: int,
        object_entity_id: int,
        predicate: str,
        value: Optional[str],
    ) -> KnowledgeStatementTriplet:
        triplet = KnowledgeStatementTriplet(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            statement_id=statement_id,
            subject_entity_id=subject_entity_id,
            object_entity_id=object_entity_id,
            predicate=predicate,
            value=value,
        )
        self.db.add(triplet)
        await self.db.flush()
        return triplet

    async def list_triplets_for_entities(
        self,
        entity_ids: Sequence[int],
    ) -> List[KnowledgeStatementTriplet]:
        unique_ids = {entity_id for entity_id in entity_ids if entity_id}
        if not unique_ids:
            return []

        stmt = select(KnowledgeStatementTriplet).where(
            KnowledgeStatementTriplet.tenant_id == self.context.tenant_id,
            KnowledgeStatementTriplet.project_id.in_(self.context.project_ids),
            or_(
                KnowledgeStatementTriplet.subject_entity_id.in_(unique_ids),
                KnowledgeStatementTriplet.object_entity_id.in_(unique_ids),
            ),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_triplets_for_statement(self, statement_id: str) -> List[KnowledgeStatementTriplet]:
        stmt = select(KnowledgeStatementTriplet).where(
            KnowledgeStatementTriplet.statement_id == statement_id,
            KnowledgeStatementTriplet.tenant_id == self.context.tenant_id,
            KnowledgeStatementTriplet.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_triplets_for_statements(self, statement_ids: Sequence[str]) -> None:
        unique_ids = {statement_id for statement_id in statement_ids if statement_id}
        if not unique_ids:
            return
        stmt = (
            delete(KnowledgeStatementTriplet)
            .where(
                KnowledgeStatementTriplet.statement_id.in_(unique_ids),
                KnowledgeStatementTriplet.tenant_id == self.context.tenant_id,
                KnowledgeStatementTriplet.project_id.in_(self.context.project_ids),
            )
        )
        await self.db.execute(stmt)

    async def list_triplets_for_signature(
        self,
        *,
        subject_entity_id: int,
        predicate: str,
        object_entity_id: Optional[int] = None,
        exclude_statement_id: Optional[str] = None,
    ) -> List[KnowledgeStatementTriplet]:
        stmt = select(KnowledgeStatementTriplet).where(
            KnowledgeStatementTriplet.tenant_id == self.context.tenant_id,
            KnowledgeStatementTriplet.project_id.in_(self.context.project_ids),
            KnowledgeStatementTriplet.subject_entity_id == subject_entity_id,
            KnowledgeStatementTriplet.predicate == predicate,
        )
        if object_entity_id is not None:
            stmt = stmt.where(
                KnowledgeStatementTriplet.object_entity_id == object_entity_id
            )
        if exclude_statement_id:
            stmt = stmt.where(
                KnowledgeStatementTriplet.statement_id != exclude_statement_id
            )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_related_triplets_with_statements(
        self,
        *,
        entity_ids: Sequence[int],
        predicates: Optional[Sequence[str]] = None,
        statement_types: Optional[Sequence[str]] = None,
    ) -> List[Tuple[KnowledgeStatementTriplet, KnowledgeStatement]]:
        """Return triplets (and their statements) related by entity.

        A triplet is included when it shares a subject or object entity from the
        provided list. Optionally filter by predicates (if supplied) and statement
        types (e.g., FACT).
        """

        unique_entities = {entity_id for entity_id in entity_ids if entity_id}
        unique_predicates = {pred for pred in predicates if pred} if predicates else None
        if not unique_entities:
            return []

        stmt = (
            select(KnowledgeStatementTriplet, KnowledgeStatement)
            .join(
                KnowledgeStatement,
                KnowledgeStatementTriplet.statement_id == KnowledgeStatement.id,
            )
            .where(
                KnowledgeStatementTriplet.tenant_id == self.context.tenant_id,
                KnowledgeStatementTriplet.project_id.in_(self.context.project_ids),
                KnowledgeStatement.tenant_id == self.context.tenant_id,
                KnowledgeStatement.project_id.in_(self.context.project_ids),
                or_(
                    KnowledgeStatementTriplet.subject_entity_id.in_(unique_entities),
                    KnowledgeStatementTriplet.object_entity_id.in_(unique_entities),
                ),
            )
        )

        if unique_predicates:
            stmt = stmt.where(
                KnowledgeStatementTriplet.predicate.in_(unique_predicates),
            )

        if statement_types:
            stmt = stmt.where(KnowledgeStatement.statement_type.in_(statement_types))

        result = await self.db.execute(stmt)
        return result.all()


class KnowledgeStatementInvalidationRepository:
    """Persistence helpers for human-in-the-loop invalidation records."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_request(
        self,
        *,
        statement_id: str,
        new_statement_id: Optional[str],
        reason: Optional[str],
        suggested_invalid_at: Optional[datetime],
        status: str,
        approved_by: Optional[str] = None,
    ) -> KnowledgeStatementInvalidation:
        request = KnowledgeStatementInvalidation(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            statement_id=statement_id,
            new_statement_id=new_statement_id,
            reason=reason,
            suggested_invalid_at=suggested_invalid_at,
            status=status,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc) if approved_by else None,
        )
        self.db.add(request)
        await self.db.flush()
        return request

    async def list_pending(self) -> List[KnowledgeStatementInvalidation]:
        stmt = select(KnowledgeStatementInvalidation).where(
            KnowledgeStatementInvalidation.tenant_id == self.context.tenant_id,
            KnowledgeStatementInvalidation.project_id.in_(self.context.project_ids),
            KnowledgeStatementInvalidation.status == "pending",
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, invalidation_id: str) -> Optional[KnowledgeStatementInvalidation]:
        stmt = select(KnowledgeStatementInvalidation).where(
            KnowledgeStatementInvalidation.id == invalidation_id,
            KnowledgeStatementInvalidation.tenant_id == self.context.tenant_id,
            KnowledgeStatementInvalidation.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_status(
        self,
        invalidation_id: str,
        *,
        status: str,
        approved_by: Optional[str] = None,
    ) -> bool:
        record = await self.get_by_id(invalidation_id)
        if not record:
            return False
        record.status = status
        if approved_by:
            record.approved_by = approved_by
            record.approved_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True


class KnowledgeEventInvalidationRepository:
    """Persistence helpers for human-in-the-loop event invalidation records."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_request(
        self,
        *,
        event_id: str,
        new_event_id: Optional[str],
        reason: Optional[str],
        suggested_invalid_at: Optional[datetime],
        status: str,
        approved_by: Optional[str] = None,
    ) -> KnowledgeEventInvalidation:
        request = KnowledgeEventInvalidation(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            event_id=event_id,
            new_event_id=new_event_id,
            reason=reason,
            suggested_invalid_at=suggested_invalid_at,
            status=status,
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc) if approved_by else None,
        )
        self.db.add(request)
        await self.db.flush()
        return request

    async def list_pending(self) -> List[KnowledgeEventInvalidation]:
        stmt = select(KnowledgeEventInvalidation).where(
            KnowledgeEventInvalidation.tenant_id == self.context.tenant_id,
            KnowledgeEventInvalidation.project_id.in_(self.context.project_ids),
            KnowledgeEventInvalidation.status == "pending",
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, invalidation_id: str) -> Optional[KnowledgeEventInvalidation]:
        stmt = select(KnowledgeEventInvalidation).where(
            KnowledgeEventInvalidation.id == invalidation_id,
            KnowledgeEventInvalidation.tenant_id == self.context.tenant_id,
            KnowledgeEventInvalidation.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_status(
        self,
        invalidation_id: str,
        *,
        status: str,
        approved_by: Optional[str] = None,
    ) -> bool:
        record = await self.get_by_id(invalidation_id)
        if not record:
            return False
        record.status = status
        if approved_by:
            record.approved_by = approved_by
            record.approved_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True


class KnowledgeEventInvalidationBatchRepository:
    """Persistence helpers for batch event invalidations."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_batch(
        self,
        items: List[Dict[str, str | None]],
        *,
        created_by: Optional[str] = None,
    ) -> KnowledgeEventInvalidationBatch:
        batch = KnowledgeEventInvalidationBatch(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            created_by=created_by,
            status="pending",
        )
        self.db.add(batch)
        await self.db.flush()

        for item in items:
            batch_item = KnowledgeEventInvalidationBatchItem(
                tenant_id=self.context.tenant_id,
                project_id=self.context.primary_project(),
                batch_id=batch.id,
                event_id=item.get("event_id"),
                new_event_id=item.get("new_event_id"),
                reason=item.get("reason"),
                suggested_invalid_at=item.get("suggested_invalid_at"),
            )
            self.db.add(batch_item)
        await self.db.flush()
        return batch

    async def get_batch(self, batch_id: str) -> Optional[KnowledgeEventInvalidationBatch]:
        stmt = select(KnowledgeEventInvalidationBatch).where(
            KnowledgeEventInvalidationBatch.id == batch_id,
            KnowledgeEventInvalidationBatch.tenant_id == self.context.tenant_id,
            KnowledgeEventInvalidationBatch.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_items(self, batch_id: str) -> List[KnowledgeEventInvalidationBatchItem]:
        stmt = select(KnowledgeEventInvalidationBatchItem).where(
            KnowledgeEventInvalidationBatchItem.batch_id == batch_id,
            KnowledgeEventInvalidationBatchItem.tenant_id == self.context.tenant_id,
            KnowledgeEventInvalidationBatchItem.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def mark_applied(self, batch_id: str, *, approved_by: Optional[str] = None) -> bool:
        batch = await self.get_batch(batch_id)
        if not batch:
            return False
        batch.status = "applied"
        batch.approved_by = approved_by
        batch.approved_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True
