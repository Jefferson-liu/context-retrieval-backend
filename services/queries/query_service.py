from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.repositories.query_repository import QueryRepository
from infrastructure.database.repositories import ProjectSummaryRepository
from schemas import Source, Clause
from langchain_openai import ChatOpenAI
from langchain_core.prompts.chat import SystemMessage
from langchain_anthropic import ChatAnthropic
from services.ai.agentic_tools.clause_former import ClauseFormer
from typing import Dict, Any, List

from config import settings

chatmodel = ChatAnthropic(temperature=0, model_name="claude-3-5-haiku-latest", api_key=settings.ANTHROPIC_API_KEY)

class QueryService:
    """Service for processing user queries, performing searches, and generating responses."""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.query_repo = QueryRepository(db, context)
        self.clause_former = ClauseFormer(chatmodel, db, context)
        self.project_summary_repo = ProjectSummaryRepository(db, context)

    async def process_query(self, query_text: str) -> Dict[str, Any]:
        """Process a query: create query, search, generate response, store results."""
        # Create query record
        query = await self.query_repo.create_query(query_text)
        
        # Create response record (placeholder)
        response = await self.query_repo.create_response(query.id)
        
        try:
            message_history = []
            project_summary = await self.project_summary_repo.get_by_project_id()
            if project_summary and project_summary.summary_text:
                project_context = SystemMessage(
                    f"You are an assistant researcher for a product manager. This is the context of the product: {project_summary.summary_text}"
                )
                message_history.append(project_context)

            response_clauses = await self.clause_former.get_response(
                message_history=message_history,
                user_query=query_text,
            )
            
            response_text = self._compose_cohesive_response(response_clauses)
            
            # Update the response with the generated text
            response = await self.query_repo.update_response_text(response.id, response_text)
            
            # Collect all sources from clauses
            all_sources = []
            for clause in response_clauses:
                all_sources.extend(clause.sources)
            
            # Create sources
            for source in all_sources:
                await self.query_repo.add_source(
                    response_id=response.id,
                    chunk_id=source.chunk_id,
                    doc_id=source.doc_id,
                    doc_name=source.doc_name,
                    snippet=source.content
                )
            
            # Update query status
            await self.query_repo.update_response_status(response.id, 'success')
            
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
            raise e

    def _compose_cohesive_response(self, clauses: List[Clause]) -> str:
        if not clauses:
            return ""

        connectors = [
            "Additionally,",
            "Furthermore,",
            "In addition,",
            "Finally,",
        ]
        sentences: List[str] = []
        connector_index = 0

        for idx, clause in enumerate(clauses):
            statement = (clause.statement or "").strip()
            if not statement:
                continue
            if idx == 0:
                sentences.append(statement)
                continue

            connector = connectors[min(connector_index, len(connectors) - 1)]
            connector_index = min(connector_index + 1, len(connectors) - 1)
            sentences.append(f"{connector} {statement}")

        return " ".join(sentences)
