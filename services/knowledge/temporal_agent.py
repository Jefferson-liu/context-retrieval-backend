from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from prompts.knowledge_graph.statement_extraction import (
    build_statement_extraction_prompt,
)
from prompts.knowledge_graph.date_extraction import (
    build_date_extraction_prompt,
)
from prompts.knowledge_graph.triplet_extraction import (
    build_triplet_extraction_prompt,
)
from schemas.knowledge_graph.enums.types import TemporalType
from schemas.knowledge_graph.raw_statement import RawStatement, RawStatementList
from schemas.knowledge_graph.temporal_range.raw_temporal_range import (
    RawTemporalRange,
    RawTemporalRangeList,
)
from schemas.knowledge_graph.entities.entity import Entity
from schemas.knowledge_graph.raw_extraction import RawExtraction
from infrastructure.ai.model_factory import build_chat_model
from config.settings import STATEMENT_EXTRACTION_MODEL, DATE_EXTRACTION_MODEL, TRIPLET_EXTRACTION_MODEL, OPENAI_API_KEY
from schemas.knowledge_graph.temporal_event import TemporalEvent
from schemas.knowledge_graph.temporal_range.temporal_validity_range import TemporalValidityRange
from openai import AsyncOpenAI
from schemas.knowledge_graph.triplets.triplet import Triplet
from tenacity import retry, stop_after_attempt, wait_random_exponential

logger = logging.getLogger(__name__)


class TemporalKnowledgeAgent:
    """Multi-step temporal knowledge extraction pipeline backed by an LLM."""
    def __init__(self) -> None:
        #TEMPORARY
        self._client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    async def get_statement_embedding(self, statement: str) -> list[float]:
        """Get the embedding of a statement."""
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=statement,
            dimensions=768,
        )
        return response.data[0].embedding
    
    async def extract_file_events(self, file_name: str, chunks: Dict[int, str], reference_timestamp: Optional[str] = None) -> tuple[List[TemporalEvent], List[Triplet], List[Entity]]:
        """Extract temporal events from file chunks."""
        all_events: list[TemporalEvent] = []
        all_triplets: list[Triplet] = []
        all_entities: list[Entity] = []
        tasks = []
        for chunk_id, chunk_text in chunks.items():
            tasks.append(
                self.process_chunk(
                    file_name=file_name,
                    chunk_text=chunk_text,
                    reference_timestamp=reference_timestamp,
                    chunk_id=chunk_id,
                )
            )
        results = await asyncio.gather(*tasks)
        for events, triplets, entities in results:
            all_events.extend(events)
            all_triplets.extend(triplets)
            all_entities.extend(entities)
        return all_events, all_triplets, all_entities
    
    async def process_chunk(
        self,
        file_name: str,
        chunk_text: str,
        reference_timestamp: Optional[str],
        chunk_id: int,
    ) -> List[TemporalEvent]:
        statements_list = await self._extract_statements(
            file_name=file_name,
            chunk_text=chunk_text,
        )
        events: list[TemporalEvent] = []
        chunk_triplets: list[Triplet] = []
        chunk_entities: list[Entity] = []
        
        async def _process_statement(statement: RawStatement) -> tuple[TemporalEvent, List[Triplet], List[Entity]]:
            temporal_range_task = self._extract_temporal_range(
                statement,
                reference_timestamp=reference_timestamp,
            )
            extraction_task = self._extract_triplets(statement.statement)
            temporal_range, raw_extraction = await asyncio.gather(temporal_range_task, extraction_task)
            if not raw_extraction:
                return None, [], []
            embedding = await self.get_statement_embedding(statement.statement)
            event = TemporalEvent(
                chunk_id=chunk_id,
                statement=statement.statement,
                valid_at=getattr(temporal_range, "valid_at", None),
                invalid_at=getattr(temporal_range, "invalid_at", None),
                embedding=embedding,
                triplets=[],
                temporal_type=statement.temporal_type,
                statement_type=statement.statement_type,
            )
            # Map raw triplets/entities to Triplet/Entity with event_id
            triplets = [Triplet.from_raw(rt, event.id) for rt in raw_extraction.triplets]
            entities = [Entity.from_raw(re, event.id) for re in raw_extraction.entities]
            event.triplets = [triplet.id for triplet in triplets]
            return event, triplets, entities
        if statements_list:
            results = await asyncio.gather(*(_process_statement(stmt) for stmt in statements_list))
            for event, triplets, entities in results:
                if not event:
                    continue
                events.append(event)
                chunk_triplets.extend(triplets)
                chunk_entities.extend(entities)
        return events, chunk_triplets, chunk_entities
    
    
    @retry(wait=wait_random_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(3))
    async def _extract_statements(
        self,
        *,
        file_name: str,
        chunk_text: str,
    ) -> List[RawStatement]:
        statement_extraction_model = build_chat_model(
            model_name=STATEMENT_EXTRACTION_MODEL,
        )
        inputs = {"document name": file_name, "chunk": chunk_text}
        prompt = build_statement_extraction_prompt(inputs)
        chain = prompt | statement_extraction_model.with_structured_output(RawStatementList)
        logger.info("Extracting STATEMENTS from chunk: %s", chunk_text)
        try:
            response = await chain.ainvoke({})
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Structured statement extraction failed: %s", exc)
            print("Structured statement extraction failed: %s" % exc)
            return []
        if not response:
            logger.info(f"No statements extracted from chunk. {chunk_text}")
            print(f"No statements extracted from chunk. {chunk_text}")
            return []

        raw_statements = getattr(response, "statements", None)
        if not raw_statements:
            logger.info(f"No statements extracted from chunk. {chunk_text}")
            print(f"No statements extracted from chunk. {chunk_text}")
            return []

        normalized: List[RawStatement] = []
        for item in raw_statements:
            if isinstance(item, RawStatement):
                normalized.append(item)
            else:
                try:
                    normalized.append(RawStatement.model_validate(item))
                except Exception as exc:  # pylint:disable=broad-except
                    logger.debug("Skipping invalid statement payload: %s", exc)
                    print("Skipping invalid statement payload: %s" % exc)
        return normalized
    
    @retry(wait=wait_random_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(3))
    async def _extract_temporal_range(
        self,
        statement: RawStatement,
        reference_timestamp: Optional[str],
    ) -> TemporalValidityRange:
        if statement.temporal_type == TemporalType.ATEMPORAL:
            return TemporalValidityRange(valid_at=None, invalid_at=None)
        
        date_extraction_model = build_chat_model(
            model_name=DATE_EXTRACTION_MODEL,
        )
        prompt = build_date_extraction_prompt(
            statement,
            reference_timestamp,
        )
        
        date_chain = (
            prompt
            | date_extraction_model.with_structured_output(RawTemporalRangeList)
        )
        
        try:
            response = await date_chain.ainvoke({})
        except Exception as exc:
            logger.warning(
                "Structured temporal range extraction failed: %s",
                exc,
            )
            print("Structured temporal range extraction failed: %s" % exc)
            return None

        temp_validity = TemporalValidityRange()
        if response:
            ranges = getattr(response, "ranges", None)
            if ranges:
                entry = ranges[0]
                temp_validity = TemporalValidityRange(
                    valid_at=getattr(entry, "valid_at", None),
                    invalid_at=getattr(entry, "invalid_at", None),
                )

        if temp_validity.valid_at is None:
            temp_validity.valid_at = datetime.now(timezone.utc)
        if statement.temporal_type == TemporalType.STATIC:
            temp_validity.invalid_at = None

        return temp_validity
    
    @retry(wait=wait_random_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(3))
    async def _extract_triplets(self, statement_text: str, max_retries: int = 3) -> Optional[RawExtraction]:
        triplet_extraction_prompt = build_triplet_extraction_prompt(statement_text)
        triplet_extraction_model = build_chat_model(
            model_name=TRIPLET_EXTRACTION_MODEL,
        )
        triplet_chain = (
            triplet_extraction_prompt
            | triplet_extraction_model.with_structured_output(RawExtraction)
        )
        for attempt in range(max_retries):
            try:
                raw_response = await triplet_chain.ainvoke({})
                return RawExtraction.model_validate(raw_response.model_dump())
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.info(f"Attempt {attempt + 1} failed with error: {str(e)}. Retrying...")
                print(f"Attempt {attempt + 1} failed with error: {str(e)}. Retrying...")
                await asyncio.sleep(1)
        raise Exception("Max retries exceeded for triplet extraction.")
