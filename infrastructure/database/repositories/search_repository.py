from typing import List, Tuple
from sqlalchemy.orm import Session
from infrastructure.database.models.documents import Chunk, Embedding, UploadedDocument

class SearchRepository:
    """Repository pattern for search-related database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_all_chunks(self) -> List[Chunk]:
        """Retrieve all chunks from the database"""
        return self.db.query(Chunk).all()
    
    def get_chunks_by_file_id(self, file_id: int) -> List[Chunk]:
        """Retrieve all chunks associated with a specific file ID"""
        return self.db.query(Chunk).filter(Chunk.doc_id == file_id).all()
    
    def get_chunk_by_id(self, chunk_id: int) -> Chunk:
        """Retrieve a single chunk by its ID"""
        return self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
    
    def get_embedding_by_chunk_id(self, chunk_id: int) -> Embedding:
        """Retrieve the embedding associated with a specific chunk ID"""
        return self.db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()
    
    def search_similar_chunks(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[Chunk, float]]:
        """Search for the most similar chunks based on a query vector using cosine similarity"""
        results = (
            self.db.query(Chunk, Embedding)
            .join(Embedding, Chunk.id == Embedding.chunk_id)
            .order_by(Embedding.embedding.cosine_distance(query_vector))
            .limit(top_k)
            .all()
        )
        return [(chunk, embedding.embedding.cosine_distance(query_vector)) for chunk, embedding in results]
    
    def tfidf_similarity_search(self, query_vector: List[float], top_k: int = 10) -> List[Tuple]:
        """
        Perform TF-IDF based similarity search using pgvector cosine distance
        
        Args:
            query_vector: TF-IDF vector representation of the query
            top_k: Number of top results to return
            
        Returns:
            List of tuples containing (id, content, chunk_id, doc_id, doc_name, similarity_score)
        """
        results = self.db.query(
            Chunk.id,
            Chunk.content,
            Chunk.doc_id,
            UploadedDocument.doc_name,
            # Calculate similarity score (1 - distance)
            (1 - Embedding.tfidf_embedding.cosine_distance(query_vector)).label('similarity_score')
        ).join(
            Embedding, Chunk.id == Embedding.chunk_id
        ).join(
            UploadedDocument, Chunk.doc_id == UploadedDocument.id
        ).filter(
            Embedding.tfidf_embedding.isnot(None)
        ).order_by(
            Embedding.tfidf_embedding.cosine_distance(query_vector)
        ).limit(top_k).all()
        
        return results
    
    def semantic_similarity_search(self, query_embedding: List[float], top_k: int = 10) -> List[Tuple]:
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