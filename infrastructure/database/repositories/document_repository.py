from typing import List, Optional
from sqlalchemy.orm import Session
from infrastructure.database.models.documents import UploadedDocument, Chunk, Embedding

class DocumentRepository:
    """Repository pattern for UploadedDocument and Chunk database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_document(self, doc_name: str, content: str, doc_size: int, doc_type: str) -> UploadedDocument:
        """Create a new document record"""
        new_document = UploadedDocument(
            doc_name=doc_name,
            content=content,
            doc_size=doc_size,
            doc_type=doc_type
        )
        self.db.add(new_document)
        return new_document

    def get_all_documents(self) -> List[UploadedDocument]:
        """Get all documents from the database"""
        return self.db.query(UploadedDocument).all()
    
    def get_document_by_id(self, document_id: int) -> Optional[UploadedDocument]:
        """Get a single document by ID"""
        return self.db.query(UploadedDocument).filter(UploadedDocument.id == document_id).first()
    
    def delete_document(self, document_id: int) -> bool:
        """Delete a document by ID"""
        document = self.get_document_by_id(document_id)
        if document:
            self.db.delete(document)
            return True
        return False

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

    def get_chunks_by_document_id(self, document_id: int) -> List[Chunk]:
        """Get all chunks associated with a specific document ID"""
        return self.db.query(Chunk).filter(Chunk.doc_id == document_id).all()
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[Chunk]:
        """Get a single chunk by its ID"""
        return self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
    
    def delete_chunk(self, chunk_id: int) -> bool:
        """Delete a chunk by its ID"""
        chunk = self.get_chunk_by_id(chunk_id)
        if chunk:
            self.db.delete(chunk)
            return True
        return False