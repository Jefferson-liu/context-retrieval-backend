from __future__ import annotations

import logging

from infrastructure.ai.user_intent import SubquestionDecomposer
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.language_models import BaseChatModel
from infrastructure.ai.tools import create_toolset
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError
from schemas import Clause, Source
from infrastructure.database.repositories import ChunkRepository, DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.ai.embedding import Embedder
from services.search.search_service import SearchService
import json

logger = logging.getLogger(__name__)

class SourceReference(BaseModel):
    doc_id: int
    chunk_id: int


class ClauseFormat(BaseModel):
    statement: str
    sources: List[SourceReference] = Field(default_factory=list)

    async def to_clause(self, chunk_repo: ChunkRepository, doc_repo: DocumentRepository) -> Clause:
        resolved_sources: List[Source] = []
        for source_ref in self.sources:
            chunk_obj = None
            if source_ref.chunk_id:
                chunk_obj = await chunk_repo.get_chunk_by_id(source_ref.chunk_id)

            if chunk_obj:
                final_chunk_id = chunk_obj.id
                content = (chunk_obj.content or "").strip()
                doc_id = chunk_obj.doc_id
            else:
                final_chunk_id = None
                doc_id = source_ref.doc_id
                content = (
                    await chunk_repo.get_content_by_chunk_id(source_ref.chunk_id)
                    if source_ref.chunk_id
                    else ""
                ) or ""

            document = await doc_repo.get_document_by_id(doc_id) if doc_id else None
            doc_name = document.doc_name if document else "Unknown Document"
            resolved_sources.append(
                Source(
                    doc_id=doc_id or source_ref.doc_id,
                    chunk_id=final_chunk_id,
                    content=content,
                    doc_name=doc_name,
                )
            )
        return Clause(
            statement=self.statement,
            sources=resolved_sources
        )
        
class ClauseFormer:
    def __init__(self, llm: BaseChatModel, db: AsyncSession, context: ContextScope):
        self.llm = llm
        self.subquestion_decomposer = SubquestionDecomposer(llm)
        self.tools = create_toolset(db, context)
        self.chunk_repo = ChunkRepository(db, context)
        self.doc_repo = DocumentRepository(db, context)
        self.search_service = SearchService(db, context, Embedder())

    async def form_clause(
        self,
        subquestion: str,
        message_history: List[BaseMessage],
        prior_clauses: Optional[List[ClauseFormat]] = None,
    ) -> Optional[ClauseFormat]:
        print(subquestion)
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
                "prior_statements": input_dict.get("prior_statements", "None yet"),
            }
        
        tool_chain = RunnableLambda(call_tool_and_format)
        prior_summary = "None yet."
        if prior_clauses:
            limited = [clause for clause in prior_clauses if clause and clause.statement][:5]
            if limited:
                prior_summary = "\n".join(f"- {clause.statement}" for clause in limited)

        prompt_template = (
            "Previously formed clauses (avoid repeating these points):\n{prior_statements}\n\n"
            "Based on this context:\n\n{context}\n\n"
            "Answer this subquestion with new information:\n{subquestion}"
        )
        prompt = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="message_history"),
            SystemMessage(
                content=(
                    "You are an expert at answering questions using the context provided to you through the search results.\n\n"
                    "Use the context to answer the question as accurately as you can. "
                    "Do not make up an answer. "
                    "Return once you can answer with cited sources. No need for excessive detail. No need for background information or context."
                    "Only use the information provided in the context. "
                    "If earlier clauses already cover a point, focus on complementary details."
                    "If you can't find the answer or the context is unusable, say 'I don't know' and do not cite any sources and do not explain why you don't know."
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
            "prior_statements": prior_summary,
        }
        messages = await message_chain.ainvoke(chain_input)
        print("Input to Anthropic LLM:")
        print("Messages object:", messages)
        response: ClauseFormat = await full_chain.ainvoke(chain_input)
        print("Clause response:", response)
        if not response or not response.sources:
            return None
        return response


    async def get_response(self, message_history: List[BaseMessage], user_query: str) -> List[Clause]:
        topics = await self.subquestion_decomposer.get_required_subquestions(message_history, user_query)
        all_clauses = []
        prior_clause_formats: List[ClauseFormat] = []
        for topic in topics:
            clause_format = await self.form_clause(topic, message_history, prior_clause_formats)
            if not clause_format:
                continue
            clause: ClauseFormat = clause_format
            if clause and clause.sources:
                #print("Formed clause:", clause)
                prior_clause_formats.append(clause)
                all_clauses.append(await clause.to_clause(self.chunk_repo, self.doc_repo))
        return all_clauses
