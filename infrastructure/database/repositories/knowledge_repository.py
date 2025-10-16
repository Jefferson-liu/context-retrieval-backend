from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.knowledge import (
    KnowledgeEntity,
    KnowledgeRelationship,
    KnowledgeRelationshipMetadata,
)


class KnowledgeEntityRepository:
    """Repository helpers for the knowledge entity table."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_entity(
        self,
        *,
        name: str,
        entity_type: str,
        description: Optional[str] = None,
    ) -> KnowledgeEntity:
        entity = KnowledgeEntity(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            name=name,
            entity_type=entity_type,
            description=description,
        )
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def get_entity_by_id(self, entity_id: int) -> Optional[KnowledgeEntity]:
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.id == entity_id,
            KnowledgeEntity.tenant_id == self.context.tenant_id,
            KnowledgeEntity.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_entity_by_name_and_type(
        self,
        *,
        name: str,
        entity_type: str,
    ) -> Optional[KnowledgeEntity]:
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.name == name,
            KnowledgeEntity.entity_type == entity_type,
            KnowledgeEntity.tenant_id == self.context.tenant_id,
            KnowledgeEntity.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_entities(
        self,
        *,
        entity_type: Optional[str] = None,
    ) -> List[KnowledgeEntity]:
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.tenant_id == self.context.tenant_id,
            KnowledgeEntity.project_id.in_(self.context.project_ids),
        )

        if entity_type:
            stmt = stmt.where(KnowledgeEntity.entity_type == entity_type)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_entity(
        self,
        entity_id: int,
        *,
        name: Optional[str] = None,
        entity_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[KnowledgeEntity]:
        entity = await self.get_entity_by_id(entity_id)
        if not entity:
            return None

        if name is not None:
            entity.name = name
        if entity_type is not None:
            entity.entity_type = entity_type
        if description is not None:
            entity.description = description

        await self.db.flush()
        return entity

    async def delete_entity(self, entity_id: int) -> bool:
        entity = await self.get_entity_by_id(entity_id)
        if not entity:
            return False

        await self.db.delete(entity)
        await self.db.flush()
        return True


class KnowledgeRelationshipRepository:
    """Repository helpers for knowledge graph relationships."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_relationship(
        self,
        *,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> KnowledgeRelationship:
        relationship = KnowledgeRelationship(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            confidence=confidence,
        )
        self.db.add(relationship)
        await self.db.flush()
        return relationship

    async def get_relationship_by_id(
        self,
        relationship_id: int,
    ) -> Optional[KnowledgeRelationship]:
        stmt = select(KnowledgeRelationship).where(
            KnowledgeRelationship.id == relationship_id,
            KnowledgeRelationship.tenant_id == self.context.tenant_id,
            KnowledgeRelationship.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_relationship_by_identity(
        self,
        *,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
    ) -> Optional[KnowledgeRelationship]:
        stmt = select(KnowledgeRelationship).where(
            KnowledgeRelationship.source_entity_id == source_entity_id,
            KnowledgeRelationship.target_entity_id == target_entity_id,
            KnowledgeRelationship.relationship_type == relationship_type,
            KnowledgeRelationship.tenant_id == self.context.tenant_id,
            KnowledgeRelationship.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_relationships(
        self,
        *,
        source_entity_ids: Optional[Sequence[int]] = None,
        target_entity_ids: Optional[Sequence[int]] = None,
        relationship_type: Optional[str] = None,
    ) -> List[KnowledgeRelationship]:
        stmt = select(KnowledgeRelationship).where(
            KnowledgeRelationship.tenant_id == self.context.tenant_id,
            KnowledgeRelationship.project_id.in_(self.context.project_ids),
        )

        if source_entity_ids:
            stmt = stmt.where(KnowledgeRelationship.source_entity_id.in_(source_entity_ids))
        if target_entity_ids:
            stmt = stmt.where(KnowledgeRelationship.target_entity_id.in_(target_entity_ids))
        if relationship_type:
            stmt = stmt.where(KnowledgeRelationship.relationship_type == relationship_type)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_relationship(
        self,
        relationship_id: int,
        *,
        relationship_type: Optional[str] = None,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[KnowledgeRelationship]:
        relationship = await self.get_relationship_by_id(relationship_id)
        if not relationship:
            return None

        if relationship_type is not None:
            relationship.relationship_type = relationship_type
        if description is not None:
            relationship.description = description
        if confidence is not None:
            relationship.confidence = confidence

        await self.db.flush()
        return relationship

    async def delete_relationship(self, relationship_id: int) -> bool:
        relationship = await self.get_relationship_by_id(relationship_id)
        if not relationship:
            return False

        await self.db.delete(relationship)
        await self.db.flush()
        return True

    async def delete_relationships_for_entity(self, entity_id: int) -> int:
        stmt = select(KnowledgeRelationship).where(
            KnowledgeRelationship.tenant_id == self.context.tenant_id,
            KnowledgeRelationship.project_id.in_(self.context.project_ids),
            or_(
                KnowledgeRelationship.source_entity_id == entity_id,
                KnowledgeRelationship.target_entity_id == entity_id,
            ),
        )
        result = await self.db.execute(stmt)
        relationships = result.scalars().all()
        if not relationships:
            return 0

        for relationship in relationships:
            await self.db.delete(relationship)
        await self.db.flush()
        return len(relationships)


class KnowledgeRelationshipMetadataRepository:
    """Repository helpers for relationship metadata entries."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def create_metadata(
        self,
        *,
        relationship_id: int,
        key: str,
        value: Optional[str] = None,
    ) -> KnowledgeRelationshipMetadata:
        metadata_entry = KnowledgeRelationshipMetadata(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            relationship_id=relationship_id,
            key=key,
            value=value,
        )
        self.db.add(metadata_entry)
        await self.db.flush()
        return metadata_entry

    async def get_metadata_by_id(
        self,
        metadata_id: int,
    ) -> Optional[KnowledgeRelationshipMetadata]:
        stmt = select(KnowledgeRelationshipMetadata).where(
            KnowledgeRelationshipMetadata.id == metadata_id,
            KnowledgeRelationshipMetadata.tenant_id == self.context.tenant_id,
            KnowledgeRelationshipMetadata.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_metadata_by_key(
        self,
        *,
        relationship_id: int,
        key: str,
    ) -> Optional[KnowledgeRelationshipMetadata]:
        stmt = select(KnowledgeRelationshipMetadata).where(
            KnowledgeRelationshipMetadata.relationship_id == relationship_id,
            KnowledgeRelationshipMetadata.key == key,
            KnowledgeRelationshipMetadata.tenant_id == self.context.tenant_id,
            KnowledgeRelationshipMetadata.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_metadata_for_relationship(
        self,
        relationship_id: int,
    ) -> List[KnowledgeRelationshipMetadata]:
        stmt = select(KnowledgeRelationshipMetadata).where(
            KnowledgeRelationshipMetadata.relationship_id == relationship_id,
            KnowledgeRelationshipMetadata.tenant_id == self.context.tenant_id,
            KnowledgeRelationshipMetadata.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_metadata(
        self,
        metadata_id: int,
        *,
        key: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Optional[KnowledgeRelationshipMetadata]:
        metadata_entry = await self.get_metadata_by_id(metadata_id)
        if not metadata_entry:
            return None

        if key is not None:
            metadata_entry.key = key
        if value is not None:
            metadata_entry.value = value

        await self.db.flush()
        return metadata_entry

    async def delete_metadata(self, metadata_id: int) -> bool:
        metadata_entry = await self.get_metadata_by_id(metadata_id)
        if not metadata_entry:
            return False

        await self.db.delete(metadata_entry)
        await self.db.flush()
        return True
