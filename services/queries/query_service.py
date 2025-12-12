from __future__ import annotations

import logging
import time
import json
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.ai.tools import create_kg_toolset
from infrastructure.ai.user_intent import SubquestionDecomposer
from config import settings
from infrastructure.context import ContextScope
from infrastructure.database.repositories import ProjectSummaryRepository
from infrastructure.database.repositories.query_repository import QueryRepository
from langchain_core.prompts.chat import SystemMessage
from langchain_anthropic import ChatAnthropic
from schemas import Clause
from schemas.source import Source
from services.ai.agentic_tools.clause_former import ClauseFormer
from services.queries import ResponseSummarizer

logger = logging.getLogger(__name__)

chatmodel = ChatAnthropic(temperature=0, model_name="claude-haiku-4-5", api_key=settings.ANTHROPIC_API_KEY)

class QueryService:
    """Service for processing user queries, performing searches, and generating responses."""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.query_repo = QueryRepository(db, context)
        self.clause_former = ClauseFormer(chatmodel, db, context)
        self.project_summary_repo = ProjectSummaryRepository(db, context)
        self.response_summarizer = ResponseSummarizer(chatmodel)
        self.subquestion_decomposer = SubquestionDecomposer()
        self.kg_tools = create_kg_toolset(db, context)

    async def process_query(self, query_text: str) -> Dict[str, Any]:
        """Process a query: create query, search, generate response, store results."""
        total_start = time.perf_counter()
        # Create query record
        query = await self.query_repo.create_query(query_text)
        
        # Create response record (placeholder)
        response = await self.query_repo.create_response(query.id)
        logger.info("Response record created for query %s: RESPONSE ID=%s", query.id, response.id)
        print("Response record created for query %s: RESPONSE ID=%s" % (query.id, response.id))
        try:
            message_history = []
            project_summary = await self.project_summary_repo.get_by_project_id()
            if project_summary and project_summary.summary_text:
                project_context = SystemMessage(
                    f"You are a researcher for a product manager. This is the context of the product: {project_summary.summary_text}"
                )
                message_history.append(project_context)
            logger.info("message history: %s", message_history)
            print("message history: %s" % message_history)
            clause_start = time.perf_counter()
            response_clauses = await self.clause_former.get_response(
                message_history=message_history,
                user_query=query_text,
            )
            clause_duration = time.perf_counter() - clause_start
            source_count = sum(len(clause.sources) for clause in response_clauses)
            logger.info(
                "Query %s clause generation: %.2fs (clauses=%d, sources=%d)",
                query.id,
                clause_duration,
                len(response_clauses),
                source_count,
            )
            print(
                "Query %s clause generation: %.2fs (clauses=%d, sources=%d)"
                % (query.id, clause_duration, len(response_clauses), source_count)
            )
            
            """summary_start = time.perf_counter()
            summary_result = await self.response_summarizer.summarize(
                user_query=query_text,
                clauses=response_clauses,
            )"""
            response_text = self._fallback_join(response_clauses)
            #summary_duration = time.perf_counter() - summary_start
            #logger.info(
            #    "Query %s summarization: %.2fs", query.id, summary_duration
            #)
            
            # Update the response with the generated text
            db_start = time.perf_counter()
            response = await self.query_repo.update_response_text(response.id, response_text)
            
            source_payloads = [
                {
                    "chunk_id": source.chunk_id,
                    "doc_id": source.doc_id,
                    "doc_name": source.doc_name,
                    "snippet": source.content,
                }
                for clause in response_clauses
                for source in clause.sources
            ]
            await self.query_repo.add_sources_bulk(response.id, source_payloads)
            
            # Update query status
            await self.query_repo.update_response_status(response.id, 'success')
            db_duration = time.perf_counter() - db_start
            total_duration = time.perf_counter() - total_start
            logger.info(
                "Query %s persistence: %.2fs | total: %.2fs",
                query.id,
                db_duration,
                total_duration,
            )
            print("Query %s persistence: %.2fs | total: %.2fs" % (query.id, db_duration, total_duration))
            
            return {
                "query_id": query.id,
                "response": response_text,
                "clauses": [
                    {
                        "statement": clause.statement,
                        "sources": [
                            {
                                "chunk_id": source.chunk_id,
                                "doc_id": source.doc_id,
                                "snippet": source.content
                            } for source in clause.sources
                        ]
                    } for clause in response_clauses
                ]
            }
        except Exception as e:
            await self.db.rollback()  # Reset session state after rollback
            await self.query_repo.update_response_status(response.id, 'failed')
            total_duration = time.perf_counter() - total_start
            logger.exception("Query %s failed after %.2fs", query.id, total_duration)
            print("Query %s failed after %.2fs" % (query.id, total_duration))
            raise e

    def _fallback_join(self, clauses: List[Clause]) -> str:
        statements = [
            (clause.statement or "").strip()
            for clause in clauses
            if clause.statement and clause.statement.strip()
        ]
        return " ".join(statements)
    
    async def process_query_kg(self, query_text: str) -> Dict[str, Any]:
        """Process a query using knowledge graph context: create query, search, generate response, store results."""
        # This method would be similar to process_query but would ensure that
        # knowledge graph context is always included in the message history.
        
        
        #First step will be the orchestrator who will instruct what to look for
        #Second step will be the searcher who will look for relevant knowledge graph facts
        #Third step will be the summarizer who will summarize the findings into a response
        
        total_start = time.perf_counter()
        query = await self.query_repo.create_query(query_text)
        response = await self.query_repo.create_response(query.id)
        logger.info("KG response record created for query %s: RESPONSE ID=%s", query.id, response.id)
        print("KG response record created for query %s: RESPONSE ID=%s" % (query.id, response.id))

        try:
            message_history = []
            project_summary = await self.project_summary_repo.get_by_project_id()
            if project_summary and project_summary.summary_text:
                message_history.append(
                    SystemMessage(
                        f"You are a researcher for a product manager. This is the context of the product: {project_summary.summary_text}"
                    )
                )

            subquestions = await self.subquestion_decomposer.get_required_subquestions(
                message_history=message_history,
                user_query=query_text,
            )
            if not subquestions:
                subquestions = [query_text]

            logger.info("KG orchestrator produced subquestions: %s", subquestions)
            print("KG orchestrator produced subquestions: %s" % subquestions)

            kg_search_tool = self.kg_tools["search_knowledge_graph"]
            clauses: List[Clause] = []

            for subquestion in subquestions:
                tool_response = await kg_search_tool.ainvoke({"query": subquestion})
                try:
                    facts = json.loads(tool_response) if tool_response else []
                except json.JSONDecodeError:
                    logger.warning("Failed to parse KG search response for '%s': %s", subquestion, tool_response)
                    print("Failed to parse KG search response for '%s': %s" % (subquestion, tool_response))
                    facts = []

                for fact in facts:
                    statement_text = (fact.get("statement") or "").strip()
                    if not statement_text:
                        continue

                    validity_parts = []
                    if fact.get("valid_at"):
                        validity_parts.append(f"valid_from={fact.get('valid_at')}")
                    if fact.get("invalid_at"):
                        validity_parts.append(f"valid_to={fact.get('invalid_at')}")
                    validity_suffix = f" [{' ,'.join(validity_parts)}]" if validity_parts else ""
                    clause_statement = f"{statement_text}{validity_suffix}"

                    source = Source(
                        doc_id=fact.get("doc_id"),
                        chunk_id=fact.get("chunk_id"),
                        content=statement_text,
                        doc_name=fact.get("doc_name") or "Knowledge Graph",
                    )
                    clauses.append(Clause(statement=clause_statement, sources=[source]))

            if not clauses:
                await self.query_repo.update_response_status(response.id, "success")
                await self.query_repo.update_response_text(
                    response.id,
                    "No matching knowledge graph facts were found for this query.",
                )
                return {
                    "query_id": query.id,
                    "response": "No matching knowledge graph facts were found for this query.",
                    "clauses": [],
                }

            summary_result = await self.response_summarizer.summarize(
                user_query=query_text,
                clauses=clauses,
            )
            response_text = summary_result.text or self._fallback_join(clauses)

            response = await self.query_repo.update_response_text(response.id, response_text)
            source_payloads = [
                {
                    "chunk_id": source.chunk_id,
                    "doc_id": source.doc_id,
                    "doc_name": source.doc_name,
                    "snippet": source.content,
                }
                for clause in clauses
                for source in clause.sources
            ]
            await self.query_repo.add_sources_bulk(response.id, source_payloads)
            await self.query_repo.update_response_status(response.id, "success")

            total_duration = time.perf_counter() - total_start
            logger.info("KG query %s succeeded in %.2fs (clauses=%d)", query.id, total_duration, len(clauses))
            print("KG query %s succeeded in %.2fs (clauses=%d)" % (query.id, total_duration, len(clauses)))

            return {
                "query_id": query.id,
                "response": response_text,
                "clauses": [
                    {
                        "statement": clause.statement,
                        "sources": [
                            {
                                "chunk_id": source.chunk_id,
                                "doc_id": source.doc_id,
                                "snippet": source.content,
                            }
                            for source in clause.sources
                        ],
                    }
                    for clause in clauses
                ],
            }
        except Exception as exc:
            await self.db.rollback()
            await self.query_repo.update_response_status(response.id, "failed")
            total_duration = time.perf_counter() - total_start
            logger.exception("KG query %s failed after %.2fs", query.id, total_duration)
            print("KG query %s failed after %.2fs" % (query.id, total_duration))
            raise exc
