from __future__ import annotations

from typing import Iterable, List, Set, Tuple, Dict

from infrastructure.database.models.knowledge import (
    KnowledgeStatement,
    KnowledgeStatementTriplet,
)
from infrastructure.database.repositories.knowledge_temporal_repository import (
    KnowledgeStatementTripletRepository,
)
from schemas.knowledge_graph.enums.types import StatementType


async def fetch_related_triplets_and_events(
    triplet_repository: KnowledgeStatementTripletRepository,
    incoming_triplets: Iterable[KnowledgeStatementTriplet],
    statement_type: StatementType = StatementType.FACT,
) -> Tuple[List[KnowledgeStatementTriplet], List[KnowledgeStatement]]:
    """Fetch existing triplets/events related to any of the incoming triplets.

    Related means:
    - Shares a subject or object entity
    - Statement type is FACT
    Returns (triplets, statements) where statements carry the temporal validity.
    """

    entity_ids: Set[int] = set()

    for triplet in incoming_triplets:
        entity_ids.update([triplet.subject_entity_id, triplet.object_entity_id])

    if not entity_ids:
        return [], []

    rows = await triplet_repository.list_related_triplets_with_statements(
        entity_ids=entity_ids,
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
