from __future__ import annotations

from typing import Dict, Optional, Tuple

from sqlalchemy import select

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.ai.knowledge_extractor import (
    ExtractedEntity,
    ExtractedRelationship,
    KnowledgeExtractor,
)
from infrastructure.database.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
    KnowledgeRelationshipMetadataRepository,
    KnowledgeRelationshipRepository,
)
from infrastructure.database.models.knowledge import (
    KnowledgeRelationship,
    KnowledgeRelationshipMetadata,
)


class KnowledgeGraphService:
    """Service that coordinates knowledge extraction and persistence."""

    DOCUMENT_METADATA_KEY = "source_document_id"

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        *,
        llm: BaseChatModel,
        entity_repository: Optional[KnowledgeEntityRepository] = None,
        relationship_repository: Optional[KnowledgeRelationshipRepository] = None,
        metadata_repository: Optional[KnowledgeRelationshipMetadataRepository] = None,
    ) -> None:
        self.db = db
        self.context = context
        self.extractor = KnowledgeExtractor(llm=llm)
        self.entity_repository = entity_repository or KnowledgeEntityRepository(db, context)
        self.relationship_repository = relationship_repository or KnowledgeRelationshipRepository(
            db, context
        )
        self.metadata_repository = metadata_repository or KnowledgeRelationshipMetadataRepository(
            db, context
        )

    async def refresh_document_knowledge(
        self,
        document_id: int,
        document_name: str,
        document_content: str,
    ) -> None:
        if not self.extractor:
            return

        await self._purge_document_knowledge(document_id)

        if not document_content.strip():
            return

        extraction = await self.extractor.extract(
            document_name=document_name or f"Document {document_id}",
            document_content=document_content,
        )
        if not extraction.entities:
            return

        entity_index: Dict[Tuple[str, str], int] = {}

        for entity in extraction.entities:
            persisted = await self._get_or_create_entity(entity)
            entity_index[(entity.name, entity.entity_type)] = persisted.id

        for relationship in extraction.relationships:
            source_id = self._resolve_entity_id(relationship.source, entity_index)
            target_id = self._resolve_entity_id(relationship.target, entity_index)
            if source_id is None or target_id is None:
                continue
            await self._create_or_update_relationship(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                document_id=document_id,
            )

    async def _purge_document_knowledge(self, document_id: int) -> None:
        stmt = (
            select(KnowledgeRelationship)
            .join(
                KnowledgeRelationshipMetadata,
                KnowledgeRelationshipMetadata.relationship_id == KnowledgeRelationship.id,
            )
            .where(
                KnowledgeRelationshipMetadata.key == self.DOCUMENT_METADATA_KEY,
                KnowledgeRelationshipMetadata.value == str(document_id),
                KnowledgeRelationship.tenant_id == self.context.tenant_id,
                KnowledgeRelationship.project_id.in_(self.context.project_ids),
            )
        )
        result = await self.db.execute(stmt)
        relationships = result.scalars().all()
        if not relationships:
            return

        entity_ids = set()
        for relationship in relationships:
            entity_ids.add(relationship.source_entity_id)
            entity_ids.add(relationship.target_entity_id)
            await self.db.delete(relationship)

        await self.db.flush()

        for entity_id in entity_ids:
            if not await self.relationship_repository.entity_has_relationships(entity_id):
                await self.entity_repository.delete_entity(entity_id)

    async def _get_or_create_entity(self, entity: ExtractedEntity):
        existing = await self.entity_repository.get_entity_by_name_and_type(
            name=entity.name,
            entity_type=entity.entity_type,
        )
        if existing:
            if entity.description and entity.description != existing.description:
                existing.description = entity.description
                await self.db.flush()
            return existing

        return await self.entity_repository.create_entity(
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
        )

    def _resolve_entity_id(
        self,
        name: str,
        entity_index: Dict[Tuple[str, str], int],
    ) -> Optional[int]:
        for (entity_name, entity_type), entity_id in entity_index.items():
            if entity_name == name:
                return entity_id
        return None

    async def _create_or_update_relationship(
        self,
        *,
        source_id: int,
        target_id: int,
        relationship: ExtractedRelationship,
        document_id: int,
    ) -> None:
        existing = await self.relationship_repository.get_relationship_by_identity(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=relationship.relationship_type,
        )

        if existing:
            updated = False
            if relationship.description is not None and relationship.description != existing.description:
                existing.description = relationship.description
                updated = True
            if updated:
                await self.db.flush()
            relationship_id = existing.id
        else:
            created = await self.relationship_repository.create_relationship(
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=relationship.relationship_type,
                description=relationship.description,
            )
            relationship_id = created.id

        await self._ensure_relationship_metadata(
            relationship_id=relationship_id,
            document_id=document_id,
        )

    async def _ensure_relationship_metadata(
        self,
        *,
        relationship_id: int,
        document_id: int,
    ) -> None:
        existing = await self.metadata_repository.get_metadata_by_key(
            relationship_id=relationship_id,
            key=self.DOCUMENT_METADATA_KEY,
        )
        if existing:
            if existing.value != str(document_id):
                existing.value = str(document_id)
                await self.db.flush()
            return

        await self.metadata_repository.create_metadata(
            relationship_id=relationship_id,
            key=self.DOCUMENT_METADATA_KEY,
            value=str(document_id),
        )
