from sqlalchemy.orm import Session
from infrastructure.database.repositories.query_repository import QueryRepository
from infrastructure.database.repositories.search_repository import SearchRepository
from infrastructure.ai.embedding import Embedder
from typing import Dict, Any

class QueryService:
    """Service for processing user queries, performing searches, and generating responses."""
    
    def __init__(self, db: Session):
        self.db = db
        self.query_repo = QueryRepository(db)
        self.search_repo = SearchRepository(db)
        self.embedder = Embedder()
    
    async def process_query(self, query_text: str) -> Dict[str, Any]:
        """Process a query: create query, search, generate response, store results."""
        # Create query record
        query = self.query_repo.create_query(query_text)
        
        try:
            # Generate embedding for search
            query_embedding = await self.embedder.generate_embedding(query_text)
            
            # Perform semantic search
            search_results = self.search_repo.semantic_vector_search(query_embedding, top_k=5)
            
            # Generate response (placeholder: summarize top results)
            response_text = self._generate_response_text(query_text, search_results)
            
            # Create response record
            response = self.query_repo.create_response(query.id, response_text, status='success')
            
            # Create sources
            for result in search_results:
                self.query_repo.add_source(
                    response_id=response.id,
                    chunk_id=result.chunk_id,
                    doc_id=result.file_id,
                    doc_name=result.filename,
                    snippet=result.content[:200]  # Snippet
                )
            
            # Update query status
            query.status = 'success'
            self.db.commit()
            
            return {
                "query_id": query.id,
                "response": response_text,
                "sources": [
                    {
                        "chunk_id": r.chunk_id,
                        "doc_name": r.filename,
                        "snippet": r.content[:200]
                    } for r in search_results
                ]
            }
        except Exception as e:
            # Handle failure
            query.status = 'failed'
            self.db.commit()
            raise e
    
    def _generate_response_text(self, query: str, results: list) -> str:
        """Generate response text from search results (placeholder logic)."""
        if not results:
            return "No relevant information found."
        
        # Simple concatenation of top results
        top_content = " ".join([r.content for r in results[:3]])
        return f"Based on the documents: {top_content[:500]}..."