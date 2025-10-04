from typing import List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.models.documents import Chunk, Embedding, Document
from schemas.responses.vector_search_result import VectorSearchResult

class SearchRepository:
    """Repository pattern for search-related database operations"""

    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context

    async def semantic_vector_search(self, query_embedding: List[float], top_k: int = 10) -> List[VectorSearchResult]:
        """
        Perform semantic similarity search using pgvector cosine distance
        
        Args:
            query_embedding: Semantic embedding vector of the query
            top_k: Number of top results to return
            
        Returns:
            List of VectorSearchResult objects containing
            (id, context, content, doc_id, doc_name, similarity_score)
        """
        stmt = select(
            Chunk.id,
            Chunk.context,
            Chunk.content,
            Chunk.doc_id,
            Document.doc_name,
            (1 - Embedding.embedding.cosine_distance(query_embedding)).label('similarity_score')
        ).join(
            Embedding, Chunk.id == Embedding.chunk_id
        ).join(
            Document, Chunk.doc_id == Document.id
        ).where(
            Embedding.embedding.isnot(None),
            Chunk.tenant_id == self.context.tenant_id,
            Chunk.project_id.in_(self.context.project_ids),
        ).order_by(
            Embedding.embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Convert to list of VectorSearchResult
        search_results = [VectorSearchResult(
            chunk_id=r[0],
            context=r[1],
            content=r[2],
            doc_id=r[3],
            doc_name=r[4],
            similarity_score=r[5]
        ) for r in rows]
        
        return search_results
    
    