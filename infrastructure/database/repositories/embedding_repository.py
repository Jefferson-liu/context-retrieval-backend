from typing import List, Optional
from sqlalchemy.orm import Session
from infrastructure.database.models.documents import Embedding


class EmbeddingRepository:
    """Repository pattern for Embeddings database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_embedding(self, chunk_id: int, embedding_vector: List[float], tfidf_vector: Optional[List[float]] = None) -> Embedding:
        """Create a new embedding record"""
        new_embedding = Embedding(
            chunk_id=chunk_id,
            embedding=embedding_vector,
            tfidf_embedding=tfidf_vector
        )
        self.db.add(new_embedding)
        return new_embedding

    def get_all_embeddings(self) -> List[Embedding]:
        """Get all embeddings from the database"""
        return self.db.query(Embedding).all()

    def update_embedding(self, chunk_id: int, **kwargs) -> Optional[Embedding]:
        """Update the semantic embedding for an existing record"""
        embedding = self.db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()
        if embedding:
            for key, value in kwargs.items():
                if hasattr(embedding, key):
                    setattr(embedding, key, value)
        return embedding
    
    def update_tfidf_embedding(self, embedding_id: int, tfidf_vector: List[float]) -> Optional[Embedding]:
        """Update the TF-IDF embedding for a specific record"""
        embedding = self.db.query(Embedding).filter(Embedding.id == embedding_id).first()
        if embedding:
            embedding.tfidf_embedding = tfidf_vector
        return embedding
    
    def clear_all_tfidf_embeddings(self) -> None:
        """Clear all TF-IDF embeddings in the database"""
        embeddings = self.db.query(Embedding).all()
        for embedding in embeddings:
            embedding.tfidf_embedding = None

    def get_embedding_by_chunk_id(self, chunk_id: int) -> Optional[Embedding]:
        """Get a single embedding by chunk ID"""
        return self.db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()