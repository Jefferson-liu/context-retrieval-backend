from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from collections import Counter, defaultdict

from scipy.spatial.distance import cosine

from infrastructure.database.models.knowledge import (
    KnowledgeStatement,
    KnowledgeStatementTriplet,
    KnowledgeEntity,
)
from infrastructure.database.repositories.knowledge_temporal_repository import (
    KnowledgeStatementRepository,
    KnowledgeStatementTripletRepository,
    KnowledgeStatementInvalidationRepository,
)
from infrastructure.database.repositories.knowledge_event_repository import (
    KnowledgeEventRepository,
)
from config import settings
from prompts.knowledge_graph.invalidation import (
    build_invalidation_prompt
)
from schemas.knowledge_graph.enums.types import TemporalType
from schemas.knowledge_graph.invalidation import InvalidationDecisionList
from infrastructure.ai.model_factory import build_chat_model    
from config.settings import KNOWLEDGE_INVALIDATION_MODEL
from schemas.knowledge_graph.temporal_event import TemporalEvent
from schemas.knowledge_graph.triplets.triplet import Triplet
from collections.abc import Coroutine
from tenacity import retry, stop_after_attempt, wait_random_exponential

logger = logging.getLogger(__name__)


class KnowledgeInvalidationService:
    """invalidation agent to retire superseded events."""

    def __init__(
        self,
        statement_repository: KnowledgeStatementRepository,
        triplet_repository: KnowledgeStatementTripletRepository,
        invalidation_repository: KnowledgeStatementInvalidationRepository,
        event_repository: KnowledgeEventRepository | None = None,
        auto_apply: bool | None = None,
        max_workers: int = 5,
    ) -> None:
        self.statement_repository = statement_repository
        self.triplet_repository = triplet_repository
        self.invalidation_repository = invalidation_repository
        self.event_repository = event_repository
        self.auto_apply = (
            settings.KNOWLEDGE_AUTO_INVALIDATION if auto_apply is None else auto_apply
        )
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._invalidation_llm = build_chat_model(
            model_name=KNOWLEDGE_INVALIDATION_MODEL,
        )
        self._similarity_threshold = 0.5
        self._top_k = 10
    
    def _coerce_response_to_bool(self, response: Any) -> bool:
        """Best-effort conversion of LLM structured output into a boolean."""
        # Handle LangChain/Bedrock message objects
        if hasattr(response, "content"):
            return self._coerce_response_to_bool(getattr(response, "content"))
        if isinstance(response, bool):
            return response
        if isinstance(response, str):
            lowered = response.strip().lower()
            if lowered in {"true", "false"}:
                return lowered == "true"
            # Heuristic for free-text answers
            negatives = (
                "not invalidate",
                "does not invalidate",
                "not invalidated",
                "does not affect",
                "not affected",
                "no invalidation",
                "cannot invalidate",
            )
            if any(neg in lowered for neg in negatives):
                return False
            positives = (
                "invalidate",
                "invalidated",
                "can invalidate",
                "refine the invalid_at",
                "invalidates",
            )
            if any(pos in lowered for pos in positives):
                return True
            return False
        if isinstance(response, dict):
            found_false = False
            found_true = False
            for value in response.values():
                coerced = self._coerce_response_to_bool(value)
                if coerced is True:
                    found_true = True
                elif coerced is False:
                    found_false = True
            if found_true:
                return True
            if found_false:
                return False
            return False
        if isinstance(response, (list, tuple)):
            found_false = False
            found_true = False
            for item in reversed(response):  # Check later items first (models sometimes append bools)
                coerced = self._coerce_response_to_bool(item)
                if coerced is True:
                    found_true = True
                elif coerced is False:
                    found_false = True
            if found_true:
                return True
            if found_false:
                return False
            return False
        return False
    
    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(1 - cosine(v1, v2))
    
    @staticmethod
    def get_incoming_temporal_bounds(
        event: TemporalEvent,
    ) -> dict[str, datetime] | None:
        """Get temporal bounds of all temporal events associated with a statement."""
        if (event.temporal_type == TemporalType.ATEMPORAL) or (event.valid_at is None):
            return None

        temporal_bounds = {"start": event.valid_at, "end": event.valid_at}

        if event.temporal_type == TemporalType.DYNAMIC:
            if event.invalid_at:
                temporal_bounds["end"] = event.invalid_at

        return temporal_bounds

    def select_events_temporally(
        self,
        triplet_events: list[tuple[Triplet, TemporalEvent]],
        temp_bounds: dict[str, datetime],
        dynamic: bool = False,
    ) -> list[tuple[Triplet, TemporalEvent]]:
        """Select temporally relevant events (static or dynamic) based on temporal bounds.

        Groups events into before, after, and overlapping categories based on their temporal bounds.

        Args:
            triplet_events: List of (Triplet, TemporalEvent) tuples to filter
            temp_bounds: Dict with 'start' and 'end' datetime bounds
            dynamic: If True, filter dynamic events; if False, filter static events
            n_window: Number of events to include before and after bounds

        Returns:
            Dict with keys '{type}_before', '{type}_after', '{type}_overlap' where type is 'dynamic' or 'static'
        """

        def _check_overlaps_dynamic(event: TemporalEvent, start: datetime, end: datetime) -> bool:
            """Check if the dynamic event overlaps with the temporal bounds of the incoming event."""
            if event.temporal_type != TemporalType.DYNAMIC:
                return False

            event_start = event.valid_at or datetime.min
            event_end = event.invalid_at

            # 1. Event contains the start
            if (event_end is not None) and (event_start <= start <= event_end):
                return True

            # 2. Ongoing event starts before the incoming start
            if (event_end is None) and (event_start <= start):
                return True

            # 3. Event starts within the incoming interval
            if start <= event_start <= end:
                return True
            return False

        # Filter by temporal type
        target_type = TemporalType.DYNAMIC if dynamic else TemporalType.STATIC
        filtered_events = [(triplet, event) for triplet, event in triplet_events if event.temporal_type == target_type]

        # Sort by valid_at timestamp
        sorted_events = sorted(filtered_events, key=lambda te: te[1].valid_at or datetime.min)

        start = temp_bounds["start"]
        end = temp_bounds["end"]

        if dynamic:
            overlap: list[tuple[Triplet, TemporalEvent]] = [
                (triplet, event) for triplet, event in sorted_events if _check_overlaps_dynamic(event, start, end)
            ]
        else:
            overlap = []
            if start != end:
                overlap = [(triplet, event) for triplet, event in sorted_events if event.valid_at and start <= event.valid_at <= end]

        return overlap
    
    def filter_by_embedding_similarity(
        self,
        reference_event: TemporalEvent,
        candidate_pairs: list[tuple[Triplet, TemporalEvent]],
    ) -> list[tuple[Triplet, TemporalEvent]]:
        """Filter triplet-event pairs by embedding similarity."""
        pairs_with_similarity = [
            (triplet, event, self.cosine_similarity(reference_event.embedding, event.embedding)) for triplet, event in candidate_pairs
        ]

        filtered_pairs = [
            (triplet, event) for triplet, event, similarity in pairs_with_similarity if similarity >= self._similarity_threshold
        ]

        sorted_pairs = sorted(filtered_pairs, key=lambda x: self.cosine_similarity(reference_event.embedding, x[1].embedding), reverse=True)

        return sorted_pairs[: self._top_k]
    
    def select_temporally_relevant_events_for_invalidation(
        self,
        incoming_event: TemporalEvent,
        candidate_triplet_events: list[tuple[Triplet, TemporalEvent]],
    ) -> list[tuple[Triplet, TemporalEvent]] | None:
        """Select relevant events to consider for invalidation."""
        # If we don't have embeddings on candidates, we cannot score similarity; skip.
        if any(not hasattr(ev, "embedding") for _, ev in candidate_triplet_events):
            return None

        # Without temporal gating, just use semantic similarity against all candidates.
        return self.filter_by_embedding_similarity(
            reference_event=incoming_event,
            candidate_pairs=candidate_triplet_events,
        )
    
    @retry(wait=wait_random_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(3))
    async def invalidation_step(
        self,
        primary_event: TemporalEvent,
        primary_triplet: Triplet,
        secondary_event: TemporalEvent,
        secondary_triplet: Triplet,
    ) -> TemporalEvent:
        """Check if primary event should be invalidated by secondary event.

        Args:
            primary_event: Event to potentially invalidate
            primary_triplet: Triplet associated with primary event
            secondary_event: Event that might cause invalidation
            secondary_triplet: Triplet associated with secondary event

        Returns:
            TemporalEvent: Updated primary event (may have invalid_at and invalidated_by set)
        """
        invalidation_prompt = build_invalidation_prompt(
            primary_statement=primary_event,
            primary_triplet=primary_triplet,
            secondary_statement=secondary_event,
            secondary_triplet=secondary_triplet,
        )
        chain = invalidation_prompt | self._invalidation_llm
        response = await chain.ainvoke({})
        decision = self._coerce_response_to_bool(response)
        logger.info(
            "Invalidation decision: primary_event=%s secondary_event=%s response=%s coerced=%s",
            primary_event.id,
            secondary_event.id,
            response,
            decision,
        )
        print(
            "Invalidation decision: primary_event=%s secondary_event=%s response=%s coerced=%s"
            % (primary_event.id, secondary_event.id, response, decision)
        )
        # Parse boolean response
        if not decision:
            return primary_event

        # Create updated event with invalidation info
        updated_event = primary_event.model_copy(
            update={
                "invalid_at": secondary_event.valid_at,
                "expired_at": datetime.now(),
                "invalidated_by": secondary_event.id,
            }
        )
        logger.info(
            "Invalidation applied: event=%s invalidated_by=%s invalid_at=%s",
            primary_event.id,
            secondary_event.id,
            secondary_event.valid_at,
        )
        print(
            "Invalidation applied: event=%s invalidated_by=%s invalid_at=%s"
            % (primary_event.id, secondary_event.id, secondary_event.valid_at)
        )
        return updated_event

    async def bi_directional_event_invalidation(
        self,
        incoming_triplet: Triplet,
        incoming_event: TemporalEvent,
        existing_triplet_events: list[tuple[Triplet, TemporalEvent]],
    ) -> tuple[TemporalEvent, list[TemporalEvent]]:
        """Validate and update temporal information for triplet events with full bidirectional invalidation.

        Args:
            incoming_triplet: The new triplet
            incoming_event: The new event associated with the triplet
            existing_triplet_events: List of existing (triplet, event) pairs to validate against

        Returns:
            tuple[TemporalEvent, list[TemporalEvent]]: (updated_incoming_event, list_of_changed_existing_events)
        """
        changed_existing_events: list[TemporalEvent] = []
        updated_incoming_event = incoming_event

        # Skip invalidation for atemporal events
        if incoming_event.temporal_type == TemporalType.ATEMPORAL:
            return incoming_event, changed_existing_events

        temporal_events = [
            (triplet, event)
            for triplet, event in existing_triplet_events
            if event.temporal_type != TemporalType.ATEMPORAL
        ]

        # Check if incoming event invalidates existing events (any temporal type)
        if temporal_events:
            tasks = [
                self.invalidation_step(
                    primary_event=existing_event,
                    primary_triplet=existing_triplet,
                    secondary_event=incoming_event,
                    secondary_triplet=incoming_triplet,
                )
                for existing_triplet, existing_event in temporal_events
            ]

            updated_events = await asyncio.gather(*tasks)

            for original_pair, updated_event in zip(temporal_events, updated_events, strict=True):
                original_event = original_pair[1]
                if (updated_event.invalid_at != original_event.invalid_at) or (
                    updated_event.invalidated_by != original_event.invalidated_by
                ):
                    changed_existing_events.append(updated_event)

        # 2. Check if existing events invalidate the incoming event (any temporal type)
        if incoming_event.invalid_at is None:
            # Only check events that occur after the incoming event
            invalidating_events = [
                (triplet, event)
                for triplet, event in temporal_events
                if (incoming_event.valid_at and event.valid_at and incoming_event.valid_at < event.valid_at)
            ]

            if invalidating_events:
                tasks = [
                    self.invalidation_step(
                        primary_event=incoming_event,
                        primary_triplet=incoming_triplet,
                        secondary_event=existing_event,
                        secondary_triplet=existing_triplet,
                    )
                    for existing_triplet, existing_event in invalidating_events
                ]

                updated_events = await asyncio.gather(*tasks)

                # Find the earliest invalidation
                valid_invalidations = [(e.invalid_at, e.invalidated_by) for e in updated_events if e.invalid_at is not None]

                if valid_invalidations:
                    earliest_invalidation = min(valid_invalidations, key=lambda x: x[0])
                    updated_incoming_event = incoming_event.model_copy(
                        update={
                            "invalid_at": earliest_invalidation[0],
                            "invalidated_by": earliest_invalidation[1],
                            "expired_at": datetime.now(),
                        }
                    )

        return updated_incoming_event, changed_existing_events
    
    @staticmethod
    def resolve_duplicate_invalidations(changed_events: list[TemporalEvent]) -> list[TemporalEvent]:
        """Resolve duplicate invalidations by selecting the most restrictive (earliest) invalidation.

        When multiple incoming events invalidate the same existing event, we should apply
        the invalidation that results in the shortest validity range (earliest invalid_at).

        Args:
            changed_events: List of events that may contain duplicates with different invalidations

        Returns:
            List of deduplicated events with the most restrictive invalidation applied
        """
        if not changed_events:
            return []

        # Count occurrences of each event ID
        id_counts = Counter(str(event.id) for event in changed_events)
        resolved_events = []
        # Group events by ID only for those with duplicates
        events_by_id = defaultdict(list)
        for event in changed_events:
            event_id = str(event.id)
            if id_counts[event_id] == 1:
                resolved_events.append(event)
            else:
                events_by_id[event_id].append(event)

        # Deduplicate only those with duplicates
        for _id, event_versions in events_by_id.items():
            invalidated_versions = [e for e in event_versions if e.invalid_at is not None]
            if not invalidated_versions:
                resolved_events.append(event_versions[0])
            else:
                most_restrictive = min(invalidated_versions, key=lambda e: (e.invalid_at if e.invalid_at is not None else datetime.max))
                resolved_events.append(most_restrictive)

        return resolved_events
    
    async def _execute_task_pool(
        self,
        tasks: list[Coroutine[Any, Any, tuple[TemporalEvent, list[TemporalEvent]]]],
        batch_size: int = 10
    ) -> list[Any]:
        """Execute tasks in batches using a pool to control concurrency.

        Args:
            tasks: List of coroutines to execute
            batch_size: Number of tasks to process concurrently

        Returns:
            List of results from all tasks
        """
        all_results = []
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            all_results.extend(batch_results)

            # Small delay between batches to prevent overload
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.1)

        return all_results

    async def process_invalidations_in_parallel(
        self,
        incoming_triplets: list[Triplet],
        incoming_events: list[TemporalEvent],
        existing_triplets: list[Triplet],
        existing_events: list[TemporalEvent],
    ) -> tuple[list[TemporalEvent], list[TemporalEvent]]:
        """Process invalidations for multiple triplets in parallel.

        Args:
            incoming_triplets: List of new triplets to process
            incoming_events: List of events associated with incoming triplets
            existing_triplets: List of existing triplets from DB
            existing_events: List of existing events from DB

        Returns:
            tuple[list[TemporalEvent], list[TemporalEvent]]:
                - List of updated incoming events (potentially invalidated)
                - List of existing events that were updated (deduplicated)
        """
        # Create mappings for faster lookups
        event_map = {str(getattr(e, "id", None)): e for e in existing_events if getattr(e, "id", None)}
        incoming_event_map = {str(t.event_id): e for t, e in zip(incoming_triplets, incoming_events, strict=False)}

        # Prepare tasks for parallel processing
        tasks = []
        for incoming_triplet in incoming_triplets:
            incoming_event = incoming_event_map[str(incoming_triplet.event_id)]

            # Get related triplet-event pairs
            related_pairs = []
            for t in existing_triplets:
                subj = getattr(t, "subject_id", getattr(t, "subject_entity_id", None))
                obj = getattr(t, "object_id", getattr(t, "object_entity_id", None))
                ev_id = getattr(t, "event_id", None) or getattr(t, "statement_id", None)
                if ev_id is None:
                    continue
                if (str(subj) == str(incoming_triplet.subject_id)) or (str(obj) == str(incoming_triplet.object_id)):
                    if str(ev_id) in event_map:
                        related_pairs.append((t, event_map[str(ev_id)]))

            # Augment candidates with embedding-based nearest events.
            if (
                self.event_repository
                and hasattr(incoming_event, "embedding")
                and incoming_event.embedding
            ):
                try:
                    nearest_events = await self.event_repository.semantic_search(
                        incoming_event.embedding,
                        top_k=5,
                    )
                    for ev in nearest_events:
                        if getattr(ev, "statement_id", None):
                            stmt_triplets = await self.triplet_repository.list_triplets_for_statement(
                                ev.statement_id
                            )
                            for trip in stmt_triplets:
                                related_pairs.append((trip, ev))
                except Exception as exc:  # pylint: disable=broad-except
                    logger.warning("Semantic search for invalidation candidates failed: %s", exc)
                    print("Semantic search for invalidation candidates failed: %s" % exc)

            # Filter for temporal relevance
            all_relevant_events = self.select_temporally_relevant_events_for_invalidation(
                incoming_event=incoming_event,
                candidate_triplet_events=related_pairs,
            )

            if not all_relevant_events:
                continue

            # Add task for parallel processing
            task = self.bi_directional_event_invalidation(
                incoming_triplet=incoming_triplet,
                incoming_event=incoming_event,
                existing_triplet_events=all_relevant_events,
            )
            tasks.append(task)

        # Process all invalidations in parallel with pooling
        if not tasks:
            return [], []

        # Use pool size based on number of workers, but cap it
        pool_size = min(self.max_workers * 2, 10)  # Adjust these numbers based on your needs
        results = await self._execute_task_pool(tasks, batch_size=pool_size)

        # Collect all results (may contain duplicates)
        updated_incoming_events = []
        all_changed_existing_events = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with error: {str(result)}")
                print(f"Task failed with error: {str(result)}")
                continue
            updated_event, changed_events = result
            updated_incoming_events.append(updated_event)
            all_changed_existing_events.extend(changed_events)

        # Resolve duplicate invalidations for existing events
        deduplicated_existing_events = self.resolve_duplicate_invalidations(all_changed_existing_events)

        # Resolve duplicate invalidations for incoming events (in case multiple triplets from same event)
        deduplicated_incoming_events = self.resolve_duplicate_invalidations(updated_incoming_events)

        return deduplicated_incoming_events, deduplicated_existing_events
