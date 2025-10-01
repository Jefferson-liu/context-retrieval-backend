from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from infrastructure.database.models.documents import Embedding, Chunk


class ChunkRepository:
    """Repository pattern for Chunking and Embedding database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_chunk(self, doc_id: int, chunk_order: int, content: str, raw_content: str) -> Chunk:
        """Create a new chunk record"""
        new_chunk = Chunk(
            doc_id=doc_id,
            chunk_order=chunk_order,
            content=content,
            raw_content=raw_content,
        )
        self.db.add(new_chunk)
        return new_chunk

    def create_embedding(self, chunk_id: int, embedding_vector: List[float]) -> Embedding:
        """Create a new embedding record"""
        new_embedding = Embedding(
            chunk_id=chunk_id,
            embedding=embedding_vector,
        )
        self.db.add(new_embedding)
        return new_embedding
    
    def get_chunks_by_doc_id(self, doc_id: int) -> List[Chunk]:
        """Get all chunks associated with a specific document ID"""
        return self.db.query(Chunk).filter(Chunk.doc_id == doc_id).all()
    
    def edit_chunk(self, chunk_id: int, **kwargs) -> Optional[Chunk]:
        """Edit an existing chunk record"""
        chunk = self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
        if chunk:
            for key, value in kwargs.items():
                if hasattr(chunk, key):
                    setattr(chunk, key, value)
        return chunk

    def update_embedding(self, chunk_id: int, **kwargs) -> Optional[Embedding]:
        """Update the embedding for an existing record"""
        embedding = self.db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()
        if embedding:
            for key, value in kwargs.items():
                if hasattr(embedding, key):
                    setattr(embedding, key, value)
        return embedding
    
    def get_embedding_by_chunk_id(self, chunk_id: int) -> Optional[Embedding]:
        """Get a single embedding by chunk ID"""
        return self.db.query(Embedding).filter(Embedding.chunk_id == chunk_id).first()
    
    def get_chunks_with_embeddings(self) -> List[Tuple]:
        return self.db.query(
            Chunk.id, Chunk.content, Embedding.embedding
        ).join(Embedding).all()
    
    def delete_chunk(self, chunk_id: int) -> bool:
        """Delete a chunk by its ID"""
        chunk = self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
        if chunk:
            self.db.delete(chunk)
            return True
        return False
    
    def delete_chunks_by_doc_id(self, doc_id: int) -> int:
        """Delete chunks by document ID"""
        chunks = self.db.query(Chunk).filter(Chunk.doc_id == doc_id).all()
        count = len(chunks)
        for chunk in chunks:
            self.db.delete(chunk)
        return count
    
    
    
    