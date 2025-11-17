from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from infrastructure.database.models.knowledge import (
    KnowledgeStatement,
    KnowledgeStatementTriplet,
)
from infrastructure.database.repositories.knowledge_temporal_repository import (
    KnowledgeStatementTripletRepository,
)
from prompts.knowledge_graph.predicate_definitions import PREDICATE_DEFINITIONS
from schemas.knowledge_graph.enums.types import StatementType


def _predicate_group_map() -> Dict[str, Set[str]]:
    """Return a simple mapping of predicates to their compatible group.

    We currently don't maintain explicit synonym groups, so each predicate maps to
    a singleton set of itself. This keeps the lookup flexible if we later add
    grouped predicates without changing the call site.
    """

    mapping: Dict[str, Set[str]] = {}
    for pred in PREDICATE_DEFINITIONS.keys():
        mapping[pred] = {pred}
    return mapping


async def fetch_related_triplets_and_events(
    triplet_repository: KnowledgeStatementTripletRepository,
    incoming_triplets: Iterable[KnowledgeStatementTriplet],
    statement_type: StatementType = StatementType.FACT,
) -> Tuple[List[KnowledgeStatementTriplet], List[KnowledgeStatement]]:
    """Fetch existing triplets/events related to any of the incoming triplets.

    Related means:
    - Shares a subject or object entity
    - Predicate is in the same predicate group (currently identity groups)
    - Statement type is FACT
    Returns (triplets, statements) where statements carry the temporal validity.
    """

    predicate_groups = _predicate_group_map()
    entity_ids: Set[int] = set()
    relevant_predicates: Set[str] = set()

    for triplet in incoming_triplets:
        entity_ids.update([triplet.subject_entity_id, triplet.object_entity_id])
        group = predicate_groups.get(triplet.predicate, {triplet.predicate})
        relevant_predicates.update(group)

    if not entity_ids or not relevant_predicates:
        return [], []

    rows = await triplet_repository.list_related_triplets_with_statements(
        entity_ids=entity_ids,
        predicates=relevant_predicates,
        statement_types=[statement_type.value] if statement_type else None,
    )

    triplets: List[KnowledgeStatementTriplet] = []
    statements_by_id: Dict[str, KnowledgeStatement] = {}
    for triplet_row, statement_row in rows:
        triplets.append(triplet_row)
        statements_by_id.setdefault(str(statement_row.id), statement_row)

    return triplets, list(statements_by_id.values())


__all__ = [
    "fetch_related_triplets_and_events",
]
