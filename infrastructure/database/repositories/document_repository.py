from typing import List, Optional
from sqlalchemy.orm import Session
from infrastructure.database.models.documents import UploadedDocument, Chunk, Embedding

class DocumentRepository:
    """Repository pattern for UploadedDocument database operations"""
    
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

    def edit_document(self, doc_id: int, **kwargs) -> Optional[UploadedDocument]:
        document = self.db.query(UploadedDocument).filter(UploadedDocument.id == doc_id).first()
        if document:
            for key, value in kwargs.items():
                setattr(document, key, value)
            self.db.commit()
            return document
        raise ValueError(f"Document with ID {doc_id} not found.")
    
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