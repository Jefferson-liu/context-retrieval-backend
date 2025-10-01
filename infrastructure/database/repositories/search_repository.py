from typing import List, Tuple
from sqlalchemy.orm import Session
from infrastructure.database.models.documents import Chunk, Embedding, UploadedDocument

class SearchRepository:
    """Repository pattern for search-related database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def semantic_vector_search(self, query_embedding: List[float], top_k: int = 10) -> List[Tuple]:
        """
        Perform semantic similarity search using pgvector cosine distance
        
        Args:
            query_embedding: Semantic embedding vector of the query
            top_k: Number of top results to return
            
        Returns:
            List of tuples containing (id, content, doc_id, doc_name, similarity_score)
        """
        results = self.db.query(
            Chunk.id,
            Chunk.content,
            Chunk.doc_id,
            UploadedDocument.doc_name,
            (1 - Embedding.embedding.cosine_distance(query_embedding)).label('similarity_score')
        ).join(
            Embedding, Chunk.id == Embedding.chunk_id
        ).join(
            UploadedDocument, Chunk.doc_id == UploadedDocument.id
        ).filter(
            Embedding.embedding.isnot(None)
        ).order_by(
            Embedding.embedding.cosine_distance(query_embedding)
        ).limit(top_k).all()
        
        return results
    
    