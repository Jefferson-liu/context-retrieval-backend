from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.knowledge import KnowledgeEntity
from infrastructure.database.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
)


@dataclass(frozen=True)
class EntityCandidate:
    id: int
    name: str
    entity_type: str
    description: Optional[str]
    confidence: float


class KnowledgeEntityResolutionService:
    """Resolve user-supplied entity text to known knowledge graph entities."""

    _DEFAULT_MIN_CONFIDENCE = 0.55
    _DEFAULT_LIMIT = 5
    _pattern = re.compile(r"[^a-z0-9]+")

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        *,
        entity_repository: Optional[KnowledgeEntityRepository] = None,
    ) -> None:
        self.db = db
        self.context = context
        self.entity_repository = entity_repository or KnowledgeEntityRepository(db, context)

    async def resolve(
        self,
        query: str,
        *,
        limit: int | None = None,
        min_confidence: float | None = None,
    ) -> list[EntityCandidate]:
        sanitized = self._normalize(query)
        if not sanitized:
            return []

        limit = limit or self._DEFAULT_LIMIT
        min_confidence = (
            min_confidence if min_confidence is not None else self._DEFAULT_MIN_CONFIDENCE
        )

        entities = await self.entity_repository.list_entities()
        query_variants = self._generate_variants(sanitized)
        scored: list[EntityCandidate] = []

        for entity in entities:
            score = self._score_against_entity(query_variants, entity)
            if score >= min_confidence:
                scored.append(
                    EntityCandidate(
                        id=entity.id,
                        name=entity.name,
                        entity_type=entity.entity_type,
                        description=entity.description,
                        confidence=round(min(score, 1.0), 4),
                    )
                )

        scored.sort(key=lambda candidate: (-candidate.confidence, candidate.name.lower()))
        return scored[:limit]

    def _normalize(self, text: str) -> str:
        lowered = text.strip().lower()
        cleaned = self._pattern.sub(" ", lowered)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _generate_variants(self, text: str) -> set[str]:
        variants = {text}
        if text.endswith("ies") and len(text) > 3:
            variants.add(text[:-3] + "y")
        if text.endswith("ses") and len(text) > 3:
            variants.add(text[:-2])
        if text.endswith("s") and len(text) > 2:
            variants.add(text[:-1])
        variants.update(part for part in text.split(" ") if part)
        return {variant for variant in variants if variant}

    def _score_against_entity(
        self,
        query_variants: Iterable[str],
        entity: KnowledgeEntity,
    ) -> float:
        entity_normalized = self._normalize(entity.name)
        entity_variants = self._generate_variants(entity_normalized)
        if not entity_variants:
            return 0.0

        seq_score = self._sequence_score(query_variants, entity_variants)
        token_score = self._token_overlap_score(query_variants, entity_variants)

        description_bonus = 0.0
        if entity.description:
            description_normalized = self._normalize(entity.description)
            description_variants = self._generate_variants(description_normalized)
            description_bonus = 0.1 * self._token_overlap_score(
                query_variants, description_variants
            )

        return min(seq_score * 0.7 + token_score * 0.3 + description_bonus, 1.0)

    def _sequence_score(
        self,
        query_variants: Iterable[str],
        entity_variants: Iterable[str],
    ) -> float:
        best = 0.0
        for query_variant in query_variants:
            for entity_variant in entity_variants:
                score = SequenceMatcher(None, query_variant, entity_variant).ratio()
                if score > best:
                    best = score
        return best

    def _token_overlap_score(
        self,
        query_variants: Iterable[str],
        entity_variants: Iterable[str],
    ) -> float:
        best = 0.0
        for query_variant in query_variants:
            query_tokens = self._tokenize(query_variant)
            if not query_tokens:
                continue
            for entity_variant in entity_variants:
                entity_tokens = self._tokenize(entity_variant)
                if not entity_tokens:
                    continue
                union = query_tokens | entity_tokens
                if not union:
                    continue
                intersection = query_tokens & entity_tokens
                score = len(intersection) / len(union)
                if score > best:
                    best = score
        return best

    def _tokenize(self, text: str) -> set[str]:
        return {token for token in text.split(" ") if token}

