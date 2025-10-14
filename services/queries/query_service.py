from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.repositories.query_repository import QueryRepository
from schemas import Source, Clause
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from services.search.search_service import SearchService
from infrastructure.ai.user_intent import SubquestionDecomposer
from infrastructure.ai.embedding import Embedder
from services.ai.agentic_tools.clause_former import ClauseFormer
from typing import Dict, Any

from config import settings

class QueryService:
    """Service for processing user queries, performing searches, and generating responses."""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.query_repo = QueryRepository(db, context)
        self.embedder = Embedder(ChatAnthropic(temperature=0, model_name="claude-3-5-sonnet-latest", api_key=settings.ANTHROPIC_API_KEY))
        self.search_service = SearchService(db, context)
        self.clause_former = ClauseFormer(ChatAnthropic(temperature=0, model_name="claude-3-5-sonnet-latest", api_key=settings.ANTHROPIC_API_KEY), db, context)
    
    async def process_query(self, query_text: str) -> Dict[str, Any]:
        """Process a query: create query, search, generate response, store results."""
        # Create query record
        query = await self.query_repo.create_query(query_text)
        
        # Create response record (placeholder)
        response = await self.query_repo.create_response(query.id)
        
        try:
            response_clauses = await self.clause_former.get_response(message_history=[], user_query=query_text)
            
            response_text = "\n\n".join([clause.statement for clause in response_clauses])
            
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