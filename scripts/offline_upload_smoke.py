"""Offline upload smoke test that bypasses LLM calls.

Runs KnowledgeGraphService.refresh_document_knowledge with a fake temporal agent
that returns canned events/triplets/entities, so you can validate the pipeline
without incurring API costs.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from infrastructure.context import ContextScope
from infrastructure.database.database import SessionLocal
from infrastructure.database.repositories import DocumentRepository
from schemas.knowledge_graph.entities.entity import Entity
from schemas.knowledge_graph.enums.types import StatementType, TemporalType
from schemas.knowledge_graph.predicate import Predicate
from schemas.knowledge_graph.temporal_event import TemporalEvent
from schemas.knowledge_graph.triplets.triplet import Triplet
from services.knowledge.knowledge_service import KnowledgeGraphService


class FakeTemporalAgent:
    """Minimal stub that mirrors TemporalKnowledgeAgent.extract_file_events."""

    async def extract_file_events(self, *, file_name: str, chunks: dict, reference_timestamp: str):
        _ = file_name, chunks, reference_timestamp  # unused in stub

        # Canned entities
        supplier = Entity(id=1, name="Acme Corp", type="Organization", description="Supplier")
        customer = Entity(id=2, name="Beta Co", type="Organization", description="Customer")

        # Canned triplet referencing the above entity names; IDs will be remapped after canonicalization.
        triplet = Triplet(
            event_id=None,  # filled below
            subject_name=supplier.name,
            subject_id=0,
            predicate=Predicate.SUPPORTS,
            object_name=customer.name,
            object_id=0,
            value="Staffing platform",
        )

        event = TemporalEvent(
            chunk_id=None,
            statement="Acme Corp provides staffing platform services to Beta Co.",
            temporal_type=TemporalType.ATEMPORAL,
            statement_type=StatementType.FACT,
            valid_at=datetime.now(timezone.utc),
            invalid_at=None,
            triplets=[triplet.id],
        )
        # wire event_id onto the triplet now that event exists
        triplet.event_id = event.id

        return [event], [triplet], [supplier, customer]


async def main():
    # Configure a throwaway context; adjust project/tenant/user to your DB.
    scope = ContextScope(tenant_id=1, project_ids=[2], user_id="offline-smoke")

    async with SessionLocal() as db:
        # Ensure a document exists for the given ID; create a fresh one each run.
        doc_repo = DocumentRepository(db, scope)
        content = "Offline smoke test content."
        doc = await doc_repo.create_document(
            doc_name="offline-smoke",
            content=content,
            doc_size=len(content),
            doc_type="text/plain",
        )

        service = KnowledgeGraphService(db=db, context=scope)
        service.temporal_agent = FakeTemporalAgent()

        result = await service.refresh_document_knowledge(
            document_id=doc.id,
            document_name=doc.doc_name,
            document_content=content,
        )
        await db.commit()
        print("Result:", result)


if __name__ == "__main__":
    asyncio.run(main())
