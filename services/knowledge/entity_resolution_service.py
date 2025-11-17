from __future__ import annotations

import re
import string
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from rapidfuzz import fuzz

from infrastructure.context import ContextScope
from schemas.knowledge_graph.entities.entity import Entity
from infrastructure.database.models.knowledge import KnowledgeEntity
from infrastructure.database.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
)
from services.knowledge.entity_normalizer import normalize_entity_name


class EntityResolutionService:
    """Resolve user-supplied entity text to known knowledge graph entities."""

    _DEFAULT_MIN_CONFIDENCE = 0.55
    _DEFAULT_LIMIT = 5
    _pattern = re.compile(r"[^a-z0-9]+")

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        entity_repository: Optional[KnowledgeEntityRepository] = None,
    ) -> None:
        self.db = db
        self.context = context
        self.entity_repository = entity_repository or KnowledgeEntityRepository(db, context)
        self._fuzzy_threshold = 80.0
        self._acronym_threshold = 98.0

    # --- Batch canonicalization helpers inspired by prior implementation ---
    async def canonicalize_batch(self, batch_entities: Sequence[Entity]) -> None:
        """Upsert extracted entities and canonicalize them using fuzzy matching."""

        if not batch_entities:
            return

        # Upsert incoming extracted entities first.
        upserted: list[KnowledgeEntity] = []
        for ent in batch_entities:
            ent_type = ent.type or "Entity"
            normalized = normalize_entity_name(ent.name)

            existing = await self.entity_repository.get_entity_by_canonical_name(
                canonical_name=normalized.canonical_name,
                entity_type=ent_type,
            )
            if not existing:
                existing = await self.entity_repository.get_entity_by_name_and_type(
                    name=ent.name,
                    entity_type=ent_type,
                )
            if not existing:
                existing = await self.entity_repository.create_entity(
                    name=ent.name,
                    entity_type=ent_type,
                    description=ent.description,
                    canonical_name=normalized.canonical_name,
                    event_id=None,
                    resolved_id=None,
                )
            upserted.append(existing)

        # Build existing canonicals keyed by type for matching and collision checks.
        canonicals_by_type: dict[str, list[KnowledgeEntity]] = {}
        for entity in await self.entity_repository.list_entities():
            canonicals_by_type.setdefault(entity.entity_type, []).append(entity)
        claimed_canonicals: dict[str, set[str]] = {
            etype: {ent.canonical_name for ent in ents}
            for etype, ents in canonicals_by_type.items()
        }

        # Group the upserted entities by type for clustering.
        type_groups: dict[str, list[KnowledgeEntity]] = {}
        for ent in upserted:
            type_groups.setdefault(ent.entity_type, []).append(ent)

        for entity_type, entities in type_groups.items():
            clusters = self._group_entities_by_fuzzy_match(entities)
            existing_canonicals = canonicals_by_type.get(entity_type, [])
            claimed = claimed_canonicals.setdefault(entity_type, set())

            for group in clusters.values():
                if not group:
                    continue
                medoid = self._medoid(group)
                if medoid is None:
                    continue

                match = self._match_to_canonical(medoid, existing_canonicals)
                if " " in medoid.name:
                    acronym = "".join(word[0] for word in medoid.name.split())
                    acronym_match = next(
                        (
                            c
                            for c in existing_canonicals
                            if fuzz.ratio(acronym, c.name) >= self._acronym_threshold
                            and " " not in c.name
                        ),
                        None,
                    )
                    if acronym_match:
                        match = acronym_match

                canonical_name = (
                    match.canonical_name if match else self._normalize_canonical(medoid.name)
                )

                for ent in group:
                    # Defensive check against canonical collisions even if not already in claimed set.
                    existing_canonical = await self.entity_repository.get_entity_by_canonical_name(
                        canonical_name=canonical_name,
                        entity_type=ent.entity_type,
                    )
                    if existing_canonical and existing_canonical.id != ent.id:
                        await self.entity_repository.update_entity(
                            ent.id,
                            resolved_id=existing_canonical.id,
                        )
                        claimed.add(canonical_name)
                        continue

                    updated = await self.entity_repository.update_entity(
                        ent.id,
                        canonical_name=canonical_name,
                    )
                    if updated:
                        claimed.add(canonical_name)

    def _clean(self, name: str) -> str:
        return name.lower().strip().translate(str.maketrans("", "", string.punctuation))

    def _group_entities_by_fuzzy_match(
        self, entities: list[KnowledgeEntity]
    ) -> dict[str, list[KnowledgeEntity]]:
        name_to_entities: dict[str, list[KnowledgeEntity]] = {}
        cleaned_map: dict[str, str] = {}
        for ent in entities:
            name_to_entities.setdefault(ent.name, []).append(ent)
            cleaned_map[ent.name] = self._clean(ent.name)
        unique_names = list(name_to_entities.keys())

        clustered: dict[str, list[KnowledgeEntity]] = {}
        used = set()
        for name in unique_names:
            if name in used:
                continue
            clustered[name] = []
            for other_name in unique_names:
                if other_name in used:
                    continue
                score = fuzz.partial_ratio(cleaned_map[name], cleaned_map[other_name])
                if score >= self._fuzzy_threshold:
                    clustered[name].extend(name_to_entities[other_name])
                    used.add(other_name)
        return clustered

    def _medoid(self, entities: list[KnowledgeEntity]) -> KnowledgeEntity | None:
        if not entities:
            return None
        n = len(entities)
        scores = [0.0] * n
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                s1 = self._clean(entities[i].name)
                s2 = self._clean(entities[j].name)
                scores[i] += fuzz.partial_ratio(s1, s2)
        max_idx = max(range(n), key=lambda idx: scores[idx])
        return entities[max_idx]

    def _match_to_canonical(
        self,
        entity: KnowledgeEntity,
        canonicals: list[KnowledgeEntity],
    ) -> KnowledgeEntity | None:
        best_score = 0.0
        best = None
        for canon in canonicals:
            score = fuzz.partial_ratio(self._clean(entity.name), self._clean(canon.name))
            if score > best_score:
                best_score = score
                best = canon
        return best if best_score >= self._fuzzy_threshold else None

    def _normalize_canonical(self, name: str) -> str:
        return self._clean(name)
