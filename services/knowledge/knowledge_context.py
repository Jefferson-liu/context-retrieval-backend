from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.repositories.document_repository import DocumentRepository
from infrastructure.database.models.documents import Document
from infrastructure.database.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
)
from infrastructure.database.repositories.knowledge_temporal_repository import (
    KnowledgeStatementRepository,
    KnowledgeStatementTripletRepository,
)
from infrastructure.database.models.knowledge import KnowledgeEntity, KnowledgeStatement, KnowledgeStatementTriplet
from services.knowledge.entity_resolution_service import (
    EntityResolutionService,
)


@dataclass(frozen=True)
class ResolvedKnowledgeEntity:
    id: int
    name: str
    entity_type: str
    description: Optional[str]
    confidence: float


@dataclass(frozen=True)
class KnowledgeContextStatement:
    statement_id: str
    primary_entity_id: int
    summary: str
    doc_id: Optional[int]
    doc_name: Optional[str]
    subject_entity_id: int
    object_entity_id: int
    predicate: str
    valid_at: Optional[datetime]
    invalid_at: Optional[datetime]


@dataclass(frozen=True)
class KnowledgeContextResult:
    entities: List[ResolvedKnowledgeEntity]
    statements: List[KnowledgeContextStatement]

    @property
    def has_statements(self) -> bool:
        return bool(self.statements)

    def to_system_message(self) -> str:
        if not self.statements:
            return ""

        lines: List[str] = ["Known product entities and relationships:"]
        statement_map: Dict[int, List[KnowledgeContextStatement]] = {}
        for statement in self.statements:
            statement_map.setdefault(statement.primary_entity_id, []).append(statement)

        for entity in self.entities:
            entity_statements = statement_map.get(entity.id)
            if not entity_statements:
                continue
            header = f"- {entity.name} ({entity.entity_type})"
            if entity.description:
                header += f": {entity.description}"
            lines.append(header)
            for stmt in entity_statements:
                citation = f" (Source: {stmt.doc_name})" if stmt.doc_name else ""
                validity: List[str] = []
                if stmt.valid_at:
                    validity.append(f"valid_from={stmt.valid_at.isoformat()}")
                if stmt.invalid_at:
                    validity.append(f"valid_to={stmt.invalid_at.isoformat()}")
                timeline = f" [{' ,'.join(validity)}]" if validity else ""
                lines.append(f"    - {stmt.summary}{timeline}{citation}")

        return "\n".join(lines)


class KnowledgeContextBuilder:
    """Derives structured knowledge statements relevant to a user query."""

    DEFAULT_MAX_ENTITIES = 3
    DEFAULT_MAX_RELATIONSHIPS = 4
    DEFAULT_MIN_CONFIDENCE = 0.4

    def __init__(
        self,
        db: AsyncSession | None,
        context: ContextScope | None,
        *,
        resolution_service: KnowledgeEntityResolutionService | None = None,
        entity_repository: KnowledgeEntityRepository | None = None,
        statement_repository: KnowledgeStatementRepository | None = None,
        triplet_repository: KnowledgeStatementTripletRepository | None = None,
        document_repository: DocumentRepository | None = None,
        max_entities: int | None = None,
        max_relationships_per_entity: int | None = None,
        min_confidence: float | None = None,
    ) -> None:
        if context is None and (
            resolution_service is None
            or entity_repository is None
            or statement_repository is None
            or triplet_repository is None
            or document_repository is None
        ):
            raise ValueError("Context must be provided when repositories are not supplied.")

        self.entity_repository = entity_repository or KnowledgeEntityRepository(db, context)  # type: ignore[arg-type]
        self.statement_repository = statement_repository or KnowledgeStatementRepository(db, context)  # type: ignore[arg-type]
        self.triplet_repository = triplet_repository or KnowledgeStatementTripletRepository(db, context)  # type: ignore[arg-type]
        self.document_repository = document_repository or DocumentRepository(db, context)  # type: ignore[arg-type]
        self.resolution_service = resolution_service or KnowledgeEntityResolutionService(
            db, context, entity_repository=self.entity_repository  # type: ignore[arg-type]
        )

        self.max_entities = max_entities or self.DEFAULT_MAX_ENTITIES
        self.max_relationships_per_entity = (
            max_relationships_per_entity or self.DEFAULT_MAX_RELATIONSHIPS
        )
        self.min_confidence = (
            min_confidence if min_confidence is not None else self.DEFAULT_MIN_CONFIDENCE
        )

    async def build_context(self, user_query: str) -> KnowledgeContextResult:
        normalized_query = (user_query or "").strip()
        if not normalized_query:
            return KnowledgeContextResult([], [])

        candidates = await self.resolution_service.resolve(
            normalized_query,
            limit=self.max_entities,
            min_confidence=self.min_confidence,
        )
        resolved_entities = self._select_entities(candidates)
        if not resolved_entities:
            return KnowledgeContextResult([], [])

        focus_entity_ids = [entity.id for entity in resolved_entities]
        triplets = await self.triplet_repository.list_triplets_for_entities(focus_entity_ids)
        if not triplets:
            return KnowledgeContextResult(resolved_entities, [])

        statement_ids = [str(triplet.statement_id) for triplet in triplets]
        statement_map = await self.statement_repository.list_statements_by_ids(statement_ids)

        entity_ids = self._collect_entity_ids(triplets, focus_entity_ids)
        entity_map = await self.entity_repository.list_entities_by_ids(entity_ids)
        doc_map = await self._load_document_map(statement_map.values())

        statements = self._build_statements(
            resolved_entities,
            triplets,
            statement_map,
            entity_map,
            doc_map,
        )
        return KnowledgeContextResult(resolved_entities, statements)

    def _select_entities(self, candidates: Sequence[EntityCandidate]) -> List[ResolvedKnowledgeEntity]:
        selected: List[ResolvedKnowledgeEntity] = []
        seen: set[int] = set()

        for candidate in candidates:
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            selected.append(
                ResolvedKnowledgeEntity(
                    id=candidate.id,
                    name=candidate.name,
                    entity_type=candidate.entity_type,
                    description=candidate.description,
                    confidence=candidate.confidence,
                )
            )
            if len(selected) >= self.max_entities:
                break
        return selected

    def _collect_entity_ids(
        self,
        triplets: Sequence[KnowledgeStatementTriplet],
        focus_ids: Sequence[int],
    ) -> set[int]:
        entity_ids: set[int] = set(focus_ids)
        for triplet in triplets:
            entity_ids.add(triplet.subject_entity_id)
            entity_ids.add(triplet.object_entity_id)
        return entity_ids

    async def _load_document_map(
        self,
        statements: Sequence[KnowledgeStatement],
    ) -> Dict[int, Document]:
        doc_ids: List[int] = []
        for statement in statements:
            if statement.document_id:
                doc_ids.append(statement.document_id)

        if not doc_ids:
            return {}

        unique_ids = list(dict.fromkeys(doc_ids))
        return await self.document_repository.get_documents_by_ids(unique_ids)

    def _build_statements(
        self,
        entities: Sequence[ResolvedKnowledgeEntity],
        triplets: Sequence[KnowledgeStatementTriplet],
        statement_map: Dict[str, KnowledgeStatement],
        entity_map: Dict[int, KnowledgeEntity],
        doc_map: Dict[int, Document],
    ) -> List[KnowledgeContextStatement]:
        statements: List[KnowledgeContextStatement] = []
        per_entity_counts: Dict[int, int] = {entity.id: 0 for entity in entities}
        entity_lookup = set(per_entity_counts.keys())

        sorted_triplets = sorted(
            triplets,
            key=lambda triplet: self._statement_sort_key(statement_map.get(str(triplet.statement_id))),
            reverse=True,
        )

        for triplet in sorted_triplets:
            statement = statement_map.get(str(triplet.statement_id))
            if not statement:
                continue
            for primary_id in (
                triplet.subject_entity_id,
                triplet.object_entity_id,
            ):
                if primary_id not in entity_lookup:
                    continue
                if per_entity_counts[primary_id] >= self.max_relationships_per_entity:
                    continue

                summary = self._summarize_triplet(
                    triplet,
                    statement,
                    primary_id,
                    entity_map,
                )
                if not summary:
                    continue

                doc_id = statement.document_id
                doc_name = doc_map.get(doc_id).doc_name if doc_id and doc_id in doc_map else None

                statements.append(
                    KnowledgeContextStatement(
                        statement_id=str(statement.id),
                        primary_entity_id=primary_id,
                        summary=summary,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        subject_entity_id=triplet.subject_entity_id,
                        object_entity_id=triplet.object_entity_id,
                        predicate=triplet.predicate,
                        valid_at=statement.valid_at,
                        invalid_at=statement.invalid_at,
                    )
                )
                per_entity_counts[primary_id] += 1

        return statements

    def _statement_sort_key(self, statement: Optional[KnowledgeStatement]):
        if not statement:
            return datetime.min.replace(tzinfo=timezone.utc)
        if statement.valid_at:
            return statement.valid_at
        return statement.updated_at or statement.created_at

    def _summarize_triplet(
        self,
        triplet: KnowledgeStatementTriplet,
        statement: KnowledgeStatement,
        primary_id: int,
        entity_map: Dict[int, KnowledgeEntity],
    ) -> Optional[str]:
        source = entity_map.get(triplet.subject_entity_id)
        target = entity_map.get(triplet.object_entity_id)
        primary = entity_map.get(primary_id)
        if not (source and target and primary):
            return None

        counterpart = target if primary_id == triplet.subject_entity_id else source
        base = f"{primary.name} {triplet.predicate} {counterpart.name}"
        if triplet.value:
            base = f"{base} ({triplet.value})"

        detail = (statement.statement or "").strip()
        if detail and detail.lower() not in base.lower():
            return f"{base}: {detail}"
        return base
