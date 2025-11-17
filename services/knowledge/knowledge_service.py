from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
from schemas.requests.text_thread import TextThreadMessageInput

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from config import settings
from infrastructure.database.repositories import (
    KnowledgeEntityRepository,
    KnowledgeEntityAliasRepository,
    KnowledgeStatementRepository,
    KnowledgeStatementTripletRepository,
    KnowledgeStatementInvalidationRepository,
    DocumentRepository,
    ChunkRepository,
)
from infrastructure.database.repositories.knowledge_event_repository import (
    KnowledgeEventRepository,
)
from infrastructure.database.repositories.knowledge_temporal_repository import (
    KnowledgeEventInvalidationBatchRepository,
)
from schemas.knowledge_graph.enums.types import TemporalType
from schemas.knowledge_graph.temporal_event import TemporalEvent
from schemas.knowledge_graph.triplets.triplet import Triplet
from services.knowledge.entity_normalizer import normalize_entity_name
from services.knowledge.invalidation_service import KnowledgeInvalidationService
from services.knowledge.temporal_agent import (
    TemporalKnowledgeAgent,
)
from infrastructure.ai.model_factory import get_dummy_call_count
from schemas.knowledge_graph.entities.raw_entity import RawEntity
from schemas.knowledge_graph.entities.entity import Entity
from schemas.knowledge_graph.enums.types import StatementType
from services.knowledge.invalidation_lookup import fetch_related_triplets_and_events
from services.knowledge.entity_resolution_service import EntityResolutionService

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Service that coordinates temporal knowledge extraction and persistence."""

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope
    ) -> dict:
        self.db = db
        self.context = context
        self.entity_repository = KnowledgeEntityRepository(db, context)
        self.alias_repository = KnowledgeEntityAliasRepository(db, context)
        self.statement_repository = KnowledgeStatementRepository(db, context)
        self.triplet_repository = KnowledgeStatementTripletRepository(
            db, context)
        self.event_repository = KnowledgeEventRepository(db, context)
        self.event_invalidation_batch_repository = KnowledgeEventInvalidationBatchRepository(
            db, context
        )
        self.document_repository = DocumentRepository(db, context)
        self.chunk_repository = ChunkRepository(db, context)
        self.temporal_agent = TemporalKnowledgeAgent()
        self.invalidation_service = KnowledgeInvalidationService(
            statement_repository=self.statement_repository,
            triplet_repository=self.triplet_repository,
            invalidation_repository=KnowledgeStatementInvalidationRepository(
                db, context),
            event_repository=self.event_repository,
            entity_repository=self.entity_repository,
            embedding_fn=self.temporal_agent.get_statement_embedding,
        )

    async def refresh_document_knowledge(
        self,
        document_id: int,
        document_name: str,
        document_content: str,
        use_invalidation: bool = True,
    ) -> None:
        document = await self.document_repository.get_document_by_id(document_id)
        if not document:
            logger.warning(
                "Document %s not found; skipping knowledge extraction.", document_id)
            print("Document %s not found; skipping knowledge extraction." % document_id)
            return

        await self.statement_repository.delete_statements_for_document(document_id)

        if not document_content.strip():
            # Called from delete_document; nothing else to process.
            return

        chunks = await self.chunk_repository.get_chunks_by_doc_id(document_id)
        if not chunks:
            chunks_payload = [(None, document_content)]
        else:
            chunks_payload = [(chunk.id, chunk.content or "")
                              for chunk in chunks]

        reference_timestamp = self._format_reference_timestamp(
            getattr(document, "upload_date", None))
        doc_display_name = document.doc_name or document_name or f"Document {document_id}"
        
        try:
            all_events, all_triplets, all_entities = await self.temporal_agent.extract_file_events(
                file_name=doc_display_name,
                chunks=dict(chunks_payload),
                reference_timestamp=reference_timestamp,
            )
            try:
                events_log = [
                    {
                        "id": str(getattr(evt, "id", None)),
                        "statement": getattr(evt, "statement", None),
                        "temporal_type": getattr(evt, "temporal_type", None),
                        "statement_type": getattr(evt, "statement_type", None),
                        "invalidated_by": getattr(evt, "invalidated_by", None),
                        "invalid_at": getattr(evt, "invalid_at", None),
                    }
                    for evt in all_events
                ]
                triplets_log = [
                    {
                        "event_id": str(getattr(tr, "event_id", None)),
                        "subject": getattr(tr, "subject_name", None),
                        "object": getattr(tr, "object_name", None),
                        "predicate": getattr(tr, "predicate", None),
                    }
                    for tr in all_triplets
                ]
                entities_log = [
                    {
                        "id": getattr(ent, "id", None),
                        "name": getattr(ent, "name", None),
                        "type": getattr(ent, "type", None),
                    }
                    for ent in all_entities
                ]
                logger.info(
                    "LLM extract_file_events details: events=%s triplets=%s entities=%s",
                    events_log,
                    triplets_log,
                    entities_log,
                )
                print(
                    "LLM extract_file_events details: events=%s triplets=%s entities=%s"
                    % (events_log, triplets_log, entities_log)
                )
            except Exception:
                pass
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Temporal agent failed for document_id=%s: %s", document_id, exc
            )
            print("Temporal agent failed for document_id=%s: %s" % (document_id, exc))
            return {"status": "error", "detail": str(exc)}

        entity_resolution_service = EntityResolutionService(
            db=self.db,
            context=self.context,
        )
        # Store extracted entities with canonicalization
        await entity_resolution_service.canonicalize_batch(all_entities)
        # Resolve entity IDs from the DB (by name/type or canonical).
        entity_id_map: dict[str, int] = {}
        for ent in all_entities:
            ent_type = ent.type or "Entity"
            cached = entity_id_map.get(ent.name)
            if cached:
                continue
            existing = await self.entity_repository.get_entity_by_name_and_type(
                name=ent.name,
                entity_type=ent_type,
            )
            if not existing:
                normalized = normalize_entity_name(ent.name)
                existing = await self.entity_repository.get_entity_by_canonical_name(
                    canonical_name=normalized.canonical_name,
                    entity_type=ent_type,
                )
            if existing:
                entity_id_map[ent.name] = existing.id

        # Update triplets to reference persisted entity IDs.
        for triplet in all_triplets:
            if triplet.subject_name in entity_id_map:
                triplet.subject_id = entity_id_map[triplet.subject_name]
            if triplet.object_name in entity_id_map:
                triplet.object_id = entity_id_map[triplet.object_name]
                
        if use_invalidation:
            final_events, changed_events = await self.batch_process_invalidation(
                all_events=all_events,
                all_triplets=all_triplets,
            )
        else:
            final_events, changed_events = all_events, []
        
        # Persist incoming events and collect their DB IDs.
        for event in final_events:
            await self._persist_event(
                document_id=document_id,
                chunk_id=event.chunk_id,
                event=event,
                triplets=all_triplets,
                entities=all_entities,
            )

        # Build invalidation payload from both updated incoming events and changed existing events.
        invalidated_events_payload = [
            {
                "event_id": str(evt.id),
                "statement": evt.statement,
                "valid_at": getattr(evt, "valid_at", None),
                "invalid_at": getattr(evt, "invalid_at", None),
            }
            for evt in final_events
            if getattr(evt, "invalidated_by", None) is not None
        ]
        invalidated_events_payload.extend(
            {
                "event_id": str(c.id),
                "statement": c.statement,
                "valid_at": getattr(c, "valid_at", None),
                "invalid_at": getattr(c, "invalid_at", None),
            }
            for c in changed_events
        )
        # Deduplicate on event_id while preserving order.
        seen_inv: set[str] = set()
        invalidated_events_payload = [
            item for item in invalidated_events_payload if not (item["event_id"] in seen_inv or seen_inv.add(item["event_id"]))
        ]

        # Handle conflicts based on auto-invalidation setting.
        if changed_events:
            if settings.KNOWLEDGE_AUTO_INVALIDATION:
                for changed in changed_events:
                    logger.info(
                        "Invalidating existing event %s due to new ingestion",
                        changed.id,
                    )
                    print("Invalidating existing event %s due to new ingestion" % changed.id)
                    updated = await self.event_repository.update_invalidation(
                        event_id=changed.id,
                        invalid_at=getattr(changed, "invalid_at", None),
                        invalidated_by=getattr(changed, "invalidated_by", None),
                        expired_at=getattr(changed, "expired_at", None),
                    )
                    if not updated:
                        logger.warning("Failed to persist invalidation for event %s", changed.id)
                        print("Failed to persist invalidation for event %s" % changed.id)
                result_payload = {"status": "success", "invalidated_events": invalidated_events_payload}
                try:
                    result_payload["dummy_call_count"] = get_dummy_call_count()
                except Exception:
                    pass
                return result_payload
            else:
                batch = await self.event_invalidation_batch_repository.create_batch(
                    [
                        {
                            "event_id": str(changed.id),
                            "new_event_id": None,
                            "reason": "Conflicts with newly ingested event",
                            "suggested_invalid_at": getattr(changed, "invalid_at", None),
                        }
                        for changed in changed_events
                    ]
                )
                logger.info(
                    "Created event invalidation batch %s for %s conflicted events",
                    batch.id,
                    len(changed_events),
                )
                print("Created event invalidation batch %s for %s conflicted events" % (batch.id, len(changed_events)))
                return {
                    "status": "conflicts",
                    "batch_id": str(batch.id),
                    "conflicts": [
                        {
                            "event_id": str(c.id),
                            "statement": c.statement,
                            "valid_at": getattr(c, "valid_at", None),
                            "invalid_at": getattr(c, "invalid_at", None),
                        }
                        for c in changed_events
                    ],
                }

        result_payload = {"status": "success", "invalidated_events": invalidated_events_payload}
        try:
            result_payload["dummy_call_count"] = get_dummy_call_count()
        except Exception:
            pass
        return result_payload

    async def refresh_text_thread_knowledge(
        self,
        thread_id: int,
        thread_title: str | None,
        thread_messages: List[TextThreadMessageInput],
    ) -> dict:
        """Extract and persist knowledge from a text thread after creating chunks (doc-backed)."""
        # Fetch chunks tied to the thread's backing document.
        chunks = await self.chunk_repository.get_chunks_by_doc_id(thread_id)
        if not chunks:
            # Fallback to raw messages if chunks are missing.
            chunks_payload = [(None, "\n".join(msg.get("text", "") for msg in thread_messages))]
        else:
            chunks_payload = [(chunk.id, chunk.content or "") for chunk in chunks]

        reference_timestamp = self._format_reference_timestamp(None)
        display_name = thread_title or f"Thread {thread_id}"

        try:
            logger.info("Text thread extraction start: file_name=%s chunks=%s", display_name, chunks_payload)
            print("Text thread extraction start: file_name=%s chunks=%s" % (display_name, chunks_payload))
            all_events, all_triplets, all_entities = await self.temporal_agent.extract_file_events(
                file_name=display_name,
                chunks=dict(chunks_payload),
                reference_timestamp=reference_timestamp,
            )
            logger.info(
                "LLM extract_file_events result: events=%s triplets=%s entities=%s",
                len(all_events),
                len(all_triplets),
                len(all_entities),
            )
            print(
                "LLM extract_file_events result: events=%s triplets=%s entities=%s"
                % (len(all_events), len(all_triplets), len(all_entities))
            )
            try:
                events_log = [
                    {
                        "id": str(getattr(evt, "id", None)),
                        "statement": getattr(evt, "statement", None),
                        "temporal_type": getattr(evt, "temporal_type", None),
                        "statement_type": getattr(evt, "statement_type", None),
                        "invalidated_by": getattr(evt, "invalidated_by", None),
                        "invalid_at": getattr(evt, "invalid_at", None),
                    }
                    for evt in all_events
                ]
                triplets_log = [
                    {
                        "event_id": str(getattr(tr, "event_id", None)),
                        "subject": getattr(tr, "subject_name", None),
                        "object": getattr(tr, "object_name", None),
                        "predicate": getattr(tr, "predicate", None),
                    }
                    for tr in all_triplets
                ]
                entities_log = [
                    {
                        "id": getattr(ent, "id", None),
                        "name": getattr(ent, "name", None),
                        "type": getattr(ent, "type", None),
                    }
                    for ent in all_entities
                ]
                logger.info(
                    "LLM extract_file_events details: events=%s triplets=%s entities=%s",
                    events_log,
                    triplets_log,
                    entities_log,
                )
                print(
                    "LLM extract_file_events details: events=%s triplets=%s entities=%s"
                    % (events_log, triplets_log, entities_log)
                )
            except Exception as e:
                print("Failed to log LLM extract_file_events details: %s" % e)
                raise e
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Temporal agent failed for thread_id=%s: %s", thread_id, exc
            )
            print("Temporal agent failed for thread_id=%s: %s" % (thread_id, exc))
            return {"status": "error", "detail": str(exc)}

        entity_resolution_service = EntityResolutionService(
            db=self.db,
            context=self.context,
        )
        await entity_resolution_service.canonicalize_batch(all_entities)

        entity_id_map: dict[str, int] = {}
        for ent in all_entities:
            ent_type = ent.type or "Entity"
            if ent.name in entity_id_map:
                continue
            existing = await self.entity_repository.get_entity_by_name_and_type(
                name=ent.name,
                entity_type=ent_type,
            )
            if not existing:
                normalized = normalize_entity_name(ent.name)
                existing = await self.entity_repository.get_entity_by_canonical_name(
                    canonical_name=normalized.canonical_name,
                    entity_type=ent_type,
                )
            if existing:
                entity_id_map[ent.name] = existing.id

        for triplet in all_triplets:
            if triplet.subject_name in entity_id_map:
                triplet.subject_id = entity_id_map[triplet.subject_name]
            if triplet.object_name in entity_id_map:
                triplet.object_id = entity_id_map[triplet.object_name]

        final_events, changed_events = await self.batch_process_invalidation(
            all_events=all_events,
            all_triplets=all_triplets,
        )
        logger.info(
            "Invalidation batch result: final_events=%s changed_events=%s",
            len(final_events),
            len(changed_events),
        )
        print(
            "Invalidation batch result: final_events=%s changed_events=%s"
            % (len(final_events), len(changed_events))
        )

        created_event_ids: set[str] = set()
        for event in final_events:
            created_id = await self._persist_event(
                document_id=None,
                chunk_id=event.chunk_id,
                event=event,
                triplets=all_triplets,
                entities=all_entities,
            )
            created_event_ids.add(created_id)

        # Build invalidation payload from both updated incoming events and changed existing events.
        invalidated_payload = [
            {
                "event_id": str(evt.id),
                "statement": evt.statement,
                "valid_at": getattr(evt, "valid_at", None),
                "invalid_at": getattr(evt, "invalid_at", None),
            }
            for evt in final_events
            if getattr(evt, "invalidated_by", None) is not None
        ]
        invalidated_payload.extend(
            {
                "event_id": str(c.id),
                "statement": c.statement,
                "valid_at": getattr(c, "valid_at", None),
                "invalid_at": getattr(c, "invalid_at", None),
            }
            for c in changed_events
        )
        seen_ids: set[str] = set()
        invalidated_payload = [
            item for item in invalidated_payload if not (item["event_id"] in seen_ids or seen_ids.add(item["event_id"]))
        ]

        if changed_events:
            if settings.KNOWLEDGE_AUTO_INVALIDATION:
                for changed in changed_events:
                    # Skip applying invalidation if the referenced event_id is not yet persisted in this batch.
                    inv_by = getattr(changed, "invalidated_by", None)
                    if inv_by and (str(inv_by) not in created_event_ids):
                        logger.warning(
                            "Skipping invalidation for event %s because invalidated_by %s was not created in this batch",
                            changed.id,
                            inv_by,
                        )
                        print("Skipping invalidation for event %s because invalidated_by %s was not created in this batch" % (changed.id, inv_by))
                        continue
                    await self.event_repository.update_invalidation(
                        event_id=changed.id,
                        invalid_at=getattr(changed, "invalid_at", None),
                        invalidated_by=getattr(changed, "invalidated_by", None),
                        expired_at=getattr(changed, "expired_at", None),
                    )
                return {
                    "status": "success",
                    "invalidated_events": invalidated_payload,
                    "batch_id": None if invalidated_payload else None,
                }
            else:
                batch = await self.event_invalidation_batch_repository.create_batch(
                    [
                        {
                            "event_id": str(changed.id),
                            "new_event_id": None,
                            "reason": "Conflicts with newly ingested event",
                            "suggested_invalid_at": getattr(changed, "invalid_at", None),
                        }
                        for changed in changed_events
                    ]
                )
                return {
                    "status": "conflicts",
                    "batch_id": str(batch.id),
                    "conflicts": [
                        {
                            "event_id": str(c.id),
                            "statement": c.statement,
                            "valid_at": getattr(c, "valid_at", None),
                            "invalid_at": getattr(c, "invalid_at", None),
                        }
                        for c in changed_events
                    ],
                }

        result_payload = {
            "status": "success",
            "invalidated_events": invalidated_payload,
        }
        if invalidated_payload:
            result_payload["batch_id"] = None
        try:
            result_payload["dummy_call_count"] = get_dummy_call_count()
        except Exception:
            pass
        return result_payload

    async def _persist_event(
        self,
        *,
        document_id: int,
        chunk_id: int | None,
        event: TemporalEvent,
        triplets: list[Triplet],
        entities: list[Entity],  # kept for parity with caller; already stored upstream
    ) -> str:
        """Persist a single event along with its statement and triplets.

        Returns:
            The created event ID (string).
        """

        # Create the knowledge_statement row (embed statement text for search).
        statement_embedding = None
        try:
            statement_embedding = await self.temporal_agent.get_statement_embedding(event.statement)
        except Exception:
            logger.warning("Failed to embed statement for persistence; continuing without embedding")
            print("Failed to embed statement for persistence; continuing without embedding")

        statement = await self.statement_repository.create_statement(
            document_id=document_id,
            chunk_id=chunk_id,
            statement_text=event.statement,
            statement_type=self._enum_value(event.statement_type),
            temporal_type=self._enum_value(event.temporal_type),
            valid_at=event.valid_at,
            invalid_at=event.invalid_at,
            embedding=statement_embedding,
        )

        # Persist triplets associated with this event.
        created_triplet_ids: list[str] = []
        linked_entity_ids: set[int] = set()
        for triplet in triplets:
            if triplet.event_id != event.id:
                continue

            # Ensure both entities exist (and have integer IDs) before creating the triplet to avoid FK failures.
            subject_entity = None
            if isinstance(triplet.subject_id, int):
                subject_entity = await self.entity_repository.get_entity_by_id(triplet.subject_id)
            if not subject_entity:
                normalized = normalize_entity_name(triplet.subject_name)
                subject_type = (
                    triplet.predicate.subject_type
                    if hasattr(triplet.predicate, "subject_type")
                    else (getattr(triplet, "subject_type", None) or triplet.__dict__.get("subject_type") or "Entity")
                )
                # Try to reuse an existing entity before creating to avoid unique collisions.
                subject_entity = await self.entity_repository.get_entity_by_name_and_type(
                    name=triplet.subject_name,
                    entity_type=subject_type,
                )
                if not subject_entity:
                    subject_entity = await self.entity_repository.get_entity_by_canonical_name(
                        canonical_name=normalized.canonical_name,
                        entity_type=subject_type,
                    )
                if not subject_entity:
                    subject_entity = await self.entity_repository.create_entity(
                        name=triplet.subject_name,
                        entity_type=subject_type,
                        description=None,
                        canonical_name=normalized.canonical_name,
                        event_id=None,
                        resolved_id=None,
                    )
                triplet.subject_id = subject_entity.id

            object_entity = None
            if isinstance(triplet.object_id, int):
                object_entity = await self.entity_repository.get_entity_by_id(triplet.object_id)
            if not object_entity:
                normalized = normalize_entity_name(triplet.object_name)
                object_type = getattr(triplet, "object_type", None) or "Entity"
                object_entity = await self.entity_repository.get_entity_by_name_and_type(
                    name=triplet.object_name,
                    entity_type=object_type,
                )
                if not object_entity:
                    object_entity = await self.entity_repository.get_entity_by_canonical_name(
                        canonical_name=normalized.canonical_name,
                        entity_type=object_type,
                    )
                if not object_entity:
                    object_entity = await self.entity_repository.create_entity(
                        name=triplet.object_name,
                        entity_type=object_type,
                        description=None,
                        canonical_name=normalized.canonical_name,
                        event_id=None,
                        resolved_id=None,
                    )
                triplet.object_id = object_entity.id

            created = await self.triplet_repository.create_triplet(
                statement_id=statement.id,
                subject_entity_id=triplet.subject_id,
                object_entity_id=triplet.object_id,
                predicate=self._enum_value(triplet.predicate),
                value=triplet.value,
            )
            created_triplet_ids.append(str(created.id))
            linked_entity_ids.update([triplet.subject_id, triplet.object_id])

        # Finally, persist the knowledge_event row with a pointer to the statement and triplets.
        created_event = await self.event_repository.create_event(
            chunk_id=chunk_id,
            statement_id=statement.id,
            triplets=created_triplet_ids,
            valid_at=event.valid_at,
            invalid_at=event.invalid_at,
            invalidated_by=getattr(event, "invalidated_by", None),
        )

        # Backfill provenance: associate entities with this event when missing.
        for entity_id in linked_entity_ids:
            existing = await self.entity_repository.get_entity_by_id(entity_id)
            if not existing:
                logger.warning(
                    "Entity %s referenced by event %s triplets not found; skipping backfill",
                    entity_id,
                    created_event.id,
                )
                print("Entity %s referenced by event %s triplets not found; skipping backfill" % (entity_id, created_event.id))
                continue
            if existing.event_id:
                continue
            await self.entity_repository.update_entity(
                entity_id,
                event_id=created_event.id,
            )

        return str(created_event.id)

    @staticmethod
    def _enum_value(value):
        """Return the raw value for enums, otherwise pass through."""
        return value.value if hasattr(value, "value") else value

        
    async def batch_process_invalidation(
        self,
        all_events: list[TemporalEvent], 
        all_triplets: list[Triplet]
    ) -> tuple[list[TemporalEvent], list[TemporalEvent]]:
        """Process invalidation for all FACT events that are temporal.

        Args:
            all_events: List of all extracted events
            all_triplets: List of all extracted triplets

        Returns:
            tuple[list[TemporalEvent], list[TemporalEvent]]:
                - final_events: All events (updated incoming events)
                - events_to_update: Existing events that need DB updates
        """
        logger.info("Starting batch invalidation processing for %s events and %s triplets", len(all_events), len(all_triplets))
        print("Starting batch invalidation processing for %s events and %s triplets" % (len(all_events), len(all_triplets)))
        def _get_fact_triplets(
            all_events: list[TemporalEvent],
            all_triplets: list[Triplet],
        ) -> list[Triplet]:
            """
            Return only those triplets whose associated event is of statement_type FACT.
            """
            fact_event_ids = {
                event.id for event in all_events if (event.statement_type == StatementType.FACT) and (event.temporal_type != TemporalType.ATEMPORAL)
            }
            return [triplet for triplet in all_triplets if triplet.event_id in fact_event_ids]
        # Prepare a list of triplets whose associated event is a FACT and not ATEMPORAL
        fact_triplets = _get_fact_triplets(all_events, all_triplets)
        logger.info("Filtered %s fact triplets for invalidation processing", len(fact_triplets))
        print("Filtered %s fact triplets for invalidation processing" % len(fact_triplets))

        if not fact_triplets:
            return all_events, []

        # Create event map for quick lookup
        all_events_map = {event.id: event for event in all_events}

        # Build aligned lists of valid triplets and their corresponding events
        fact_events: list[TemporalEvent] = []
        valid_fact_triplets: list[Triplet] = []
        for triplet in fact_triplets:
            # Handle potential None event_id and ensure type safety
            if triplet.event_id is not None:
                event = all_events_map.get(triplet.event_id)
                if event:
                    fact_events.append(event)
                    valid_fact_triplets.append(triplet)
                else:
                    print(
                        f"Warning: Could not find event for fact_triplet with event_id {triplet.event_id}")
            else:
                print(
                    f"Warning: Fact triplet {triplet.id} has no event_id, skipping invalidation")

        if not valid_fact_triplets:
            logger.info("No valid fact triplets found for invalidation processing")
            print("No valid fact triplets found for invalidation processing")
            return all_events, []

        # Batch fetch all related existing triplets and events
        existing_triplets, existing_statements = await fetch_related_triplets_and_events(
            triplet_repository=self.triplet_repository,
            incoming_triplets=valid_fact_triplets,
            statement_type=StatementType.FACT,
        )
        statement_ids = [stmt.id for stmt in existing_statements if getattr(stmt, "id", None)]
        existing_events = []
        logger.info("Fetching existing events for %s statements", len(statement_ids))
        print("Fetching existing events for %s statements" % len(statement_ids))
        logger.info("Existing statements: %s", existing_statements)
        print("Existing statements: %s" % existing_statements)
        logger.info("Existing Triplets: %s", existing_triplets)
        print("Existing Triplets: %s" % existing_triplets)
        if statement_ids:
            existing_events = await self.event_repository.list_events_for_statement_ids(statement_ids)
        if existing_events:
            statement_lookup = {
                str(stmt.id): stmt
                for stmt in existing_statements
                if getattr(stmt, "id", None)
            }
            converted_existing_events: list[TemporalEvent] = []
            for ev in existing_events:
                stmt = statement_lookup.get(str(getattr(ev, "statement_id", None))) or getattr(ev, "statement_ref", None)
                if not stmt:
                    logger.warning("Existing event %s missing statement for invalidation; skipping", getattr(ev, "id", None))
                    print("Existing event %s missing statement for invalidation; skipping" % getattr(ev, "id", None))
                    continue
                stmt_type = stmt.statement_type
                temp_type = stmt.temporal_type
                if isinstance(stmt_type, str):
                    stmt_type = StatementType(stmt_type)
                if isinstance(temp_type, str):
                    temp_type = TemporalType(temp_type)
                converted_existing_events.append(
                    TemporalEvent(
                        id=ev.id,
                        statement_id=getattr(ev, "statement_id", None),
                        statement=stmt.statement,
                        statement_type=stmt_type,
                        temporal_type=temp_type,
                        valid_at=ev.valid_at or stmt.valid_at,
                        invalid_at=ev.invalid_at or stmt.invalid_at,
                        invalidated_by=getattr(ev, "invalidated_by", None),
                        chunk_id=getattr(ev, "chunk_id", None),
                    )
                )
            existing_events = converted_existing_events

        # Process all invalidations in parallel
        updated_incoming_fact_events, changed_existing_events = await self.invalidation_service.process_invalidations_in_parallel(
            incoming_triplets=valid_fact_triplets,
            incoming_events=fact_events,
            existing_triplets=existing_triplets,
            existing_events=existing_events,
        )

        # Create mapping for efficient updates
        updated_incoming_event_map = {
            event.id: event for event in updated_incoming_fact_events}

        # Reconstruct final events list with updates applied
        final_events = []
        for original_event in all_events:
            if original_event.id in updated_incoming_event_map:
                final_events.append(
                    updated_incoming_event_map[original_event.id])
            else:
                final_events.append(original_event)
        return final_events, changed_existing_events

    async def apply_event_invalidation_batch(self, batch_id: str, *, approved_by: str | None = None) -> bool:
        batch = await self.event_invalidation_batch_repository.get_batch(batch_id)
        if not batch or batch.status != "pending":
            return False
        items = await self.event_invalidation_batch_repository.list_items(batch_id)
        for item in items:
            logger.info(
                "Applying invalidation for event %s (new_event_id=%s)",
                item.event_id,
                item.new_event_id,
            )
            print("Applying invalidation for event %s (new_event_id=%s)" % (item.event_id, item.new_event_id))
            updated = await self.event_repository.update_invalidation(
                event_id=item.event_id,
                invalid_at=item.suggested_invalid_at or datetime.now(timezone.utc),
                invalidated_by=item.new_event_id,
                expired_at=datetime.now(timezone.utc),
            )
            if not updated:
                logger.warning("Failed to persist batch invalidation for event %s", item.event_id)
                print("Failed to persist batch invalidation for event %s" % item.event_id)
        await self.event_invalidation_batch_repository.mark_applied(
            batch_id, approved_by=approved_by
        )
        return True

    @staticmethod
    def _format_reference_timestamp(timestamp: Optional[datetime]) -> str:
        value = timestamp or datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    @staticmethod
    def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        candidate = raw.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            logger.debug("Unable to parse timestamp value: %s", raw)
            print("Unable to parse timestamp value: %s" % raw)
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
