from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.repositories.query_repository import QueryRepository
from infrastructure.ai.embedding import Embedder
from infrastructure.vector_store import create_vector_store
from typing import Dict, Any

class QueryService:
    """Service for processing user queries, performing searches, and generating responses."""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.query_repo = QueryRepository(db, context)
        self.embedder = Embedder()
        self.vector_store = create_vector_store(db)
    
    async def process_query(self, query_text: str) -> Dict[str, Any]:
        """Process a query: create query, search, generate response, store results."""
        # Create query record
        query = await self.query_repo.create_query(query_text)
        
        # Generate embedding for search
        query_embedding = await self.embedder.generate_embedding(query_text)
        
        # Perform semantic search
        search_results = await self.vector_store.search(
            query_embedding,
            tenant_id=self.context.tenant_id,
            project_ids=self.context.project_ids,
            top_k=5,
        )
        
        # Create response record (placeholder)
        response = await self.query_repo.create_response(query.id)
        
        try:
            # Generate response using LLM
            response_text = await self._generate_response_text(query_text, search_results)
            
            # Update the response with the generated text
            response = await self.query_repo.update_response_text(response.id, response_text)
                            
            # Create sources
            for result in search_results:
                await self.query_repo.add_source(
                    response_id=response.id,
                    chunk_id=result.chunk_id,
                    doc_id=result.doc_id,
                    doc_name=result.doc_name,
                    snippet=result.content
                )
            
            # Update query status
            await self.query_repo.update_response_status(response.id, 'success')
            
            return {
                "query_id": query.id,
                "response": response_text,
                "sources": [
                    {
                        "chunk_id": r.chunk_id,
                        "doc_name": r.doc_name,
                        "snippet": r.content
                    } for r in search_results
                ]
            }
        except Exception as e:
            await self.db.rollback()  # Reset session state after rollback
            await self.query_repo.update_response_status(response.id, 'failed')
            raise e
    
    async def _generate_response_text(self, query: str, results: list) -> str:
        """Generate response text from search results using LLM."""
        if not results:
            return "No relevant information found."
        
        # Prepare context from search results
        context = "\n\n".join([f"Document: {r.doc_name}\nContext: {r.context}" for r in results[:3]])
        
        prompt = f"Based on the following context, answer the query: {query}\n\nBe very opinionated about the context, if user disagrees, ask to clarify\n\nContext:\n{context}\n\nAnswer:"
        
        response = await self.embedder.llm_provider.get_response(prompt, max_tokens=1024)
        return response