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
            content = await chunk_repo.get_content_by_chunk_id(source_ref.chunk_id)
            document = await doc_repo.get_document_by_id(source_ref.doc_id)
            doc_name = document.doc_name if document else "Unknown Document"
            resolved_sources.append(
                Source(
                    doc_id=source_ref.doc_id,
                    chunk_id=source_ref.chunk_id,
                    content=content or "",
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

    async def form_clause(self, subquestion: str) -> ClauseFormat:
        print(subquestion)
        search_tool = self.tools["search_chunks"]
        
        async def call_tool_and_format(input_dict):
            subquestion = input_dict["subquestion"]
            tool_result = await search_tool.ainvoke({"query": subquestion})
            context = json.loads(tool_result)
            return {
                "context": context,
                "subquestion": subquestion
            }
        
        tool_chain = RunnableLambda(call_tool_and_format)
        prompt_template = "Based on this context\n\n{context}\n\nAnswer this question:\n\nquestion: {subquestion}"
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(
                content=(
                    "You are an expert at answering questions using the context provided to you through the search results.\n\n"
                    "Use the context to answer the question as accurately as you can. "
                    "Do not make up an answer. "
                    "Return once you can answer with cited sources. No need for excessive detail. No need for background information or context."
                    "Only use the information provided in the context"
                    "If you can't find the answer or the context is unusable, say 'I don't know' and do not cite any sources and do not explain why you don't know."
                )
            ),
            HumanMessagePromptTemplate.from_template(prompt_template),
        ])
        clause_llm = self.llm.with_structured_output(ClauseFormat)
        full_chain = tool_chain | prompt | clause_llm
        message_chain = tool_chain | prompt
        messages = await message_chain.ainvoke({"subquestion": subquestion})
        print("Input to Anthropic LLM:")
        print("Messages object:", messages)
        response: ClauseFormat = await full_chain.ainvoke({"subquestion": subquestion})
        print("Clause response:", response)
        if not response or not response.sources:
            return None
        return response


    async def get_response(self, message_history: List[BaseMessage], user_query: str) -> List[Clause]:
        topics = await self.subquestion_decomposer.get_required_subquestions(message_history, user_query)
        all_clauses = []
        for topic in topics:
            clause: ClauseFormat = await self.form_clause(topic)
            if clause and clause.sources:
                print("Formed clause:", clause)
                all_clauses.append(await clause.to_clause(self.chunk_repo, self.doc_repo))
        return all_clauses