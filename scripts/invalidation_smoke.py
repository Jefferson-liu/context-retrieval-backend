"""Manual smoke test for KnowledgeInvalidationService without pytest.

Runs a small scenario: an existing dynamic event "Olga is the designer" and an
incoming dynamic event "Jeff is the designer". We stub the invalidation step to
always invalidate the primary when compared, then print the results.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from schemas.knowledge_graph.enums.types import TemporalType
from schemas.knowledge_graph.predicate import Predicate
from schemas.knowledge_graph.temporal_event import TemporalEvent
from schemas.knowledge_graph.triplets.triplet import Triplet
from services.knowledge.invalidation_service import KnowledgeInvalidationService

# Ensure project root on path when running directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


class _StubStatementRepo:
    pass


class _StubTripletRepo:
    async def list_triplets_for_statement(self, statement_id):
        return []


class _StubInvalidationRepo:
    pass


async def main():
    # Incoming event/triplet
    incoming_event = TemporalEvent(
        id=uuid.uuid4(),
        statement="Jeff is the designer",
        temporal_type=TemporalType.DYNAMIC,
        statement_type=TemporalType.FACT,
        valid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        embedding=[1.0, 0.0, 0.0],
        invalid_at=None,
        triplets=[],
    )
    incoming_triplet = Triplet(
        event_id=incoming_event.id,
        subject_name="Jeff",
        subject_id=1,
        predicate=Predicate.IS_A,
        object_name="Designer",
        object_id=2,
    )

    # Existing event/triplet
    existing_event = TemporalEvent(
        id=uuid.uuid4(),
        statement="Olga is the designer",
        temporal_type=TemporalType.DYNAMIC,
        statement_type=TemporalType.FACT,
        valid_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        embedding=[0.9, 0.0, 0.0],
        invalid_at=None,
        triplets=[],
    )
    existing_triplet = Triplet(
        event_id=existing_event.id,
        subject_name="Olga",
        subject_id=1,
        predicate=Predicate.IS_A,
        object_name="Designer",
        object_id=2,
    )

    service = KnowledgeInvalidationService(
        statement_repository=_StubStatementRepo(),
        triplet_repository=_StubTripletRepo(),
        invalidation_repository=_StubInvalidationRepo(),
        event_repository=None,
        embedding_fn=None,
    )

    # Stub invalidation_step to always invalidate primary with secondary.
    async def _fake_invalidation_step(primary_event, primary_triplet, secondary_event, secondary_triplet, primary_triplet_str=None, secondary_triplet_str=None):
        return primary_event.model_copy(
            update={
                "invalid_at": secondary_event.valid_at,
                "invalidated_by": secondary_event.id,
                "expired_at": datetime.now(timezone.utc),
            }
        )

    service.invalidation_step = _fake_invalidation_step  # type: ignore

    updated_incoming, changed_existing = await service.process_invalidations_in_parallel(
        incoming_triplets=[incoming_triplet],
        incoming_events=[incoming_event],
        existing_triplets=[existing_triplet],
        existing_events=[existing_event],
    )

    print("Updated incoming events:", updated_incoming)
    print("Changed existing events:", changed_existing)
    if changed_existing:
        ev = changed_existing[0]
        print("Existing event invalidated_by:", ev.invalidated_by)
        print("Existing event invalid_at:", ev.invalid_at)


if __name__ == "__main__":
    asyncio.run(main())
