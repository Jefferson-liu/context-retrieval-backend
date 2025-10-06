import json

import logging

from infrastructure.ai.query_logic import QueryReasoner
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from infrastructure.ai.tools import create_toolset
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError
from schemas import Clause, Source
from infrastructure.database.repositories import ChunkRepository, DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope

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
        
class QueryReasoningEngine:
    def __init__(self, llm: BaseChatModel, db: AsyncSession, context: ContextScope):
        self.llm = llm
        self.query_reasoner = QueryReasoner(llm)
        self.tools = create_toolset(db, context)
        self.chunk_repo = ChunkRepository(db, context)
        self.doc_repo = DocumentRepository(db, context)

    async def form_clause(self, subquestion: str) -> ClauseFormat:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(
                content=(
                    "You are an expert at answering questions using the tools provided for you.\n\n"
                    "Use the tools to find relevant information to answer the question as accurately as you can. "
                    "Cite your sources using (doc_id, chunk_id)."
                    "Do not make up an answer. "
                    "Return once you can answer with cited sources. No need for excessive detail. No need for background information or context."
                    "Only use the information provided by the tools"
                )
            ),
            MessagesPlaceholder(variable_name="messages"),
            HumanMessage(
                content=(
                    "Answer this question:\n\n"
                    f"question: {subquestion}"
                )
            ),
        ])

        search_agent = create_react_agent(
            self.llm,
            tools=self.tools,
            response_format=ClauseFormat,
            prompt=prompt,
        )
        raw_result = await search_agent.ainvoke(
            {"input": subquestion},
            config={"recursion_limit": 10},
        )
        logger.debug("Raw clause result from agent: type=%s payload=%s", type(raw_result), raw_result)
        clause = self._coerce_clause_format(raw_result["structured_response"] if isinstance(raw_result, dict) else raw_result)
        if clause:
            return clause
        logger.error(
            "Failed to coerce clause: type=%s payload=%s", type(raw_result), raw_result
        )
        raise TypeError(f"Unexpected clause result type: {type(raw_result)}")
    

    async def get_response(self, message_history: List[BaseMessage], user_query: str) -> List[Clause]:
        #topics = await self.query_reasoner.get_required_subquestions(message_history, user_query)
        #all_clauses = []
        #for topic in topics:
        #    clause: ClauseFormat = await self.form_clause(topic)
        #    all_clauses.append(await clause.to_clause(self.chunk_repo, self.doc_repo))
        #return all_clauses
        
        response = await self.form_clause(user_query)
        return [await response.to_clause(self.chunk_repo, self.doc_repo)]

    def _coerce_clause_format(self, raw_result: Any) -> Optional[ClauseFormat]:
        if isinstance(raw_result, ClauseFormat):
            return raw_result
        if isinstance(raw_result, dict):
            direct = self._try_parse_clause_dict(raw_result)
            if direct:
                return direct
            messages = raw_result.get("messages")
            if messages:
                return self._parse_clause_from_messages(messages)
        if isinstance(raw_result, list):
            return self._parse_clause_from_messages(raw_result)
        return None

    def _try_parse_clause_dict(self, data: Dict[str, Any]) -> Optional[ClauseFormat]:
        for key in ("output", "final_output", "result"):
            payload = data.get(key)
            clause = self._coerce_payload_to_clause(payload)
            if clause:
                return clause
        # If dict itself looks like clause payload
        clause = self._coerce_payload_to_clause(data)
        if clause:
            return clause
        return None

    def _parse_clause_from_messages(self, messages: List[Any]) -> Optional[ClauseFormat]:
        for message in reversed(messages):
            clause = self._parse_clause_from_message(message)
            if clause:
                return clause
        return None

    def _parse_clause_from_message(self, message: Any) -> Optional[ClauseFormat]:
        additional = getattr(message, "additional_kwargs", None) or {}

        # Check tool_calls (OpenAI v1)
        tool_calls = additional.get("tool_calls")
        if tool_calls:
            for call in reversed(tool_calls):
                function = call.get("function") if isinstance(call, dict) else None
                clause = self._coerce_payload_to_clause(function.get("arguments") if function else None)
                if clause:
                    return clause

        # Check legacy function_call
        function_call = additional.get("function_call")
        if function_call:
            clause = self._coerce_payload_to_clause(function_call.get("arguments"))
            if clause:
                return clause

        # Check response_metadata/output keys
        response_metadata = getattr(message, "response_metadata", None) or {}
        clause = self._coerce_payload_to_clause(response_metadata.get("output"))
        if clause:
            return clause

        # Finally, inspect message.content
        content = getattr(message, "content", None)
        clause = self._coerce_payload_to_clause(content)
        if clause:
            return clause

        return None

    def _coerce_payload_to_clause(self, payload: Any) -> Optional[ClauseFormat]:
        data = self._coerce_payload_to_dict(payload)
        if not data:
            return None
        try:
            return ClauseFormat.model_validate(data)
        except ValidationError:
            return None

    def _coerce_payload_to_dict(self, payload: Any) -> Optional[Dict[str, Any]]:
        if payload is None:
            return None
        if isinstance(payload, ClauseFormat):
            return payload.model_dump()
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return None
        if isinstance(payload, list):
            for item in reversed(payload):
                data = self._coerce_payload_to_dict(item)
                if data:
                    return data
            return None
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        if hasattr(payload, "dict"):
            return payload.dict()
        return None