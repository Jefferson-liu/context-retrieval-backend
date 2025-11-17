import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Ensure project root on sys.path for test imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from services.knowledge.invalidation_service import KnowledgeInvalidationService
from schemas.knowledge_graph.temporal_event import TemporalEvent
from schemas.knowledge_graph.triplets.triplet import Triplet
from schemas.knowledge_graph.predicate import Predicate
from schemas.knowledge_graph.enums.types import TemporalType


class _StubStatementRepo:
    pass


class _StubTripletRepo:
    async def list_triplets_for_statement(self, statement_id):
        return []


class _StubInvalidationRepo:
    pass


@pytest.mark.asyncio
async def test_invalidation_semantic_similarity_updates_existing_event(monkeypatch):
    incoming_event = TemporalEvent(
        id=uuid.uuid4(),
        statement="Jeff is the designer",
        temporal_type=TemporalType.DYNAMIC,
        statement_type=None,  # not used in this path
        valid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        embedding=[1.0, 0.0, 0.0],
        invalid_at=None,
    )
    existing_event = TemporalEvent(
        id=uuid.uuid4(),
        statement="Olga is the designer",
        temporal_type=TemporalType.DYNAMIC,
        statement_type=None,
        valid_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        embedding=[0.9, 0.0, 0.0],
        invalid_at=None,
    )

    incoming_triplet = Triplet(
        event_id=incoming_event.id,
        subject_name="Jeff",
        subject_id=1,
        predicate=Predicate.IS_A,
        object_name="Designer",
        object_id=2,
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
    )

    async def _fake_invalidation_step(primary_event, primary_triplet, secondary_event, secondary_triplet):
        return primary_event.model_copy(
            update={
                "invalid_at": secondary_event.valid_at,
                "invalidated_by": secondary_event.id,
                "expired_at": datetime.now(timezone.utc),
            }
        )

    monkeypatch.setattr(service, "invalidation_step", _fake_invalidation_step)

    updated_incoming, changed_existing = await service.process_invalidations_in_parallel(
        incoming_triplets=[incoming_triplet],
        incoming_events=[incoming_event],
        existing_triplets=[existing_triplet],
        existing_events=[existing_event],
    )

    assert updated_incoming == []  # no incoming invalidations expected in this scenario
    assert len(changed_existing) == 1
    assert changed_existing[0].invalidated_by == incoming_event.id
    assert changed_existing[0].invalid_at == incoming_event.valid_at
