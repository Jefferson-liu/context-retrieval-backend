from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Set

from infrastructure.ai.tools import create_toolset
from infrastructure.ai.user_intent import SubquestionDecomposer
from infrastructure.context import ContextScope
from infrastructure.database.repositories import ChunkRepository, DocumentRepository
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field
from schemas import Clause, Source
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import CLAUSE_FORMING_MODEL
from infrastructure.ai.model_factory import build_chat_model

logger = logging.getLogger(__name__)

class SourceReference(BaseModel):
    doc_id: int
    chunk_id: int


class ClauseFormat(BaseModel):
    statement: str
    sources: List[SourceReference] = Field(default_factory=list)
        
class ClauseFormer:
    MAX_SUBQUESTIONS = 4
    MAX_PARALLEL_SUBQUERIES = 3

    def __init__(self, db: AsyncSession, context: ContextScope):
        self.llm = build_chat_model(model_name=CLAUSE_FORMING_MODEL)
        self.subquestion_decomposer = SubquestionDecomposer()
        self.tools = create_toolset(db, context)
        self.chunk_repo = ChunkRepository(db, context)
        self.doc_repo = DocumentRepository(db, context)

    async def form_clause(
        self,
        subquestion: str,
        message_history: List[BaseMessage],
    ) -> Optional[ClauseFormat]:
        logger.debug("Forming clause for subquestion: %s", subquestion)
        search_tool = self.tools["search_chunks"]
        
        async def call_tool_and_format(input_dict):
            subquestion = input_dict["subquestion"]
            history = input_dict["message_history"]
            tool_result = await search_tool.ainvoke({"query": subquestion})
            context = json.loads(tool_result)
            return {
                "context": context,
                "subquestion": subquestion,
                "message_history": history,
            }
        
        tool_chain = RunnableLambda(call_tool_and_format)
        prompt_template = (
            "Here are the search results"
            "\n\n{context}\n\n"
            "Answer this question:\n{subquestion}"
        )
        prompt = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="message_history"),
            SystemMessage(
                content=(
                    "You are a question answering agent. The user will provide you with a question and a set of search results."
                    "Your job is to answer the user's question using only information from the search results. "
                    "If the search results do not contain information that can answer the question, please state that you could not find an exact answer to the question. "
                    "Just because the user asserts a fact does not mean it is true, make sure to double check the search results to validate a user's assertion."
                )
            ),
            HumanMessagePromptTemplate.from_template(prompt_template),
        ])
        clause_llm = self.llm.with_structured_output(ClauseFormat)
        full_chain = tool_chain | prompt | clause_llm
        message_chain = tool_chain | prompt
        chain_input = {
            "subquestion": subquestion,
            "message_history": message_history,
        }
        messages = await message_chain.ainvoke(chain_input)
        logger.info("LLM prompt for '%s': %s", subquestion, messages)
        response: ClauseFormat = await full_chain.ainvoke(chain_input)
        logger.info("Clause response for '%s': %s", subquestion, response)
        if not response or not response.sources:
            return None
        return response


    async def get_response(self, message_history: List[BaseMessage], user_query: str) -> List[Clause]:
        total_start = time.perf_counter()
        decomposition_start = time.perf_counter()
        topics = await self.subquestion_decomposer.get_required_subquestions(message_history, user_query)
        decomposition_duration = time.perf_counter() - decomposition_start
        logger.info(
            "ClauseFormer: decomposition produced %d raw topics in %.2fs -> %s",
            len(topics),
            decomposition_duration,
            topics,
        )
        if not topics:
            total_duration = time.perf_counter() - total_start
            logger.info("ClauseFormer: no topics to process (total %.2fs)", total_duration)
            return []

        generation_start = time.perf_counter()
        semaphore = asyncio.Semaphore(self.MAX_PARALLEL_SUBQUERIES)
        prior_clause_formats: List[ClauseFormat] = []
        prior_lock = asyncio.Lock()

        async def process_topic(topic: str) -> Optional[ClauseFormat]:
            async with semaphore:
                clause_format = await self.form_clause(topic, message_history)
                if clause_format:
                    async with prior_lock:
                        prior_clause_formats.append(clause_format)
                return clause_format

        clause_candidates = await asyncio.gather(*(process_topic(topic) for topic in topics))
        filtered_formats = [clause for clause in clause_candidates if clause and clause.sources]
        clause_generation_duration = time.perf_counter() - generation_start

        hydration_start = time.perf_counter()
        hydrated_clauses = await self._hydrate_clauses(filtered_formats)
        hydration_duration = time.perf_counter() - hydration_start

        total_duration = time.perf_counter() - total_start
        logger.info(
            "ClauseFormer: clause generation %.2fs, hydration %.2fs, total %.2fs (clauses=%d)",
            clause_generation_duration,
            hydration_duration,
            total_duration,
            len(hydrated_clauses),
        )
        return hydrated_clauses

    async def _hydrate_clauses(self, clause_formats: Sequence[ClauseFormat]) -> List[Clause]:
        if not clause_formats:
            return []

        chunk_ids = {
            source_ref.chunk_id
            for clause in clause_formats
            for source_ref in clause.sources
            if source_ref.chunk_id
        }
        chunk_map = await self.chunk_repo.get_chunks_by_ids(chunk_ids)

        doc_ids = {
            source_ref.doc_id
            for clause in clause_formats
            for source_ref in clause.sources
            if source_ref.doc_id
        }
        for chunk in chunk_map.values():
            if chunk.doc_id:
                doc_ids.add(chunk.doc_id)
        doc_map = await self.doc_repo.get_documents_by_ids(doc_ids)

        hydrated_clauses: List[Clause] = []
        for clause_format in clause_formats:
            resolved_sources: List[Source] = []
            for source_ref in clause_format.sources:
                chunk_obj = chunk_map.get(source_ref.chunk_id) if source_ref.chunk_id else None
                final_chunk_id = chunk_obj.id if chunk_obj else None
                doc_id = chunk_obj.doc_id if chunk_obj else source_ref.doc_id
                content = (chunk_obj.content or "").strip() if chunk_obj else ""
                document = doc_map.get(doc_id) if doc_id else None
                doc_name = document.doc_name if document else "Unknown Document"
                resolved_sources.append(
                    Source(
                        doc_id=doc_id or source_ref.doc_id,
                        chunk_id=final_chunk_id,
                        content=content,
                        doc_name=doc_name,
                    )
                )
            hydrated_clauses.append(
                Clause(
                    statement=clause_format.statement,
                    sources=resolved_sources,
                )
            )

        return hydrated_clauses
