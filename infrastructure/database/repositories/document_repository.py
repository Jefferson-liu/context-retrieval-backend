from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.models.documents import Document, Chunk, Embedding

class DocumentRepository:
    """Repository pattern for Document database operations"""
    
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
    
    async def create_document(self, doc_name: str, content: str, doc_size: int, doc_type: str) -> Document:
        """Create a new document record"""
        new_document = Document(
            doc_name=doc_name,
            content=content,
            doc_size=doc_size,
            doc_type=doc_type,
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            created_by_user_id=self.context.user_id,
        )
        self.db.add(new_document)
        await self.db.flush()
        return new_document

    async def edit_document(self, doc_id: int, **kwargs) -> Optional[Document]:
        stmt = select(Document).where(
            Document.id == doc_id,
            Document.tenant_id == self.context.tenant_id,
            Document.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        if document:
            for key, value in kwargs.items():
                setattr(document, key, value)
            await self.db.commit()
            return document
        raise ValueError(f"Document with ID {doc_id} not found.")
    
    async def get_all_documents(self) -> List[Document]:
        """Get all documents from the database"""
        stmt = select(Document).where(
            Document.tenant_id == self.context.tenant_id,
            Document.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_document_by_id(self, document_id: int) -> Optional[Document]:
        """Get a single document by ID"""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == self.context.tenant_id,
            Document.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def delete_document(self, document_id: int) -> bool:
        """Delete a document by ID"""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == self.context.tenant_id,
            Document.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        if document:
            await self.db.delete(document)
            await self.db.commit()
            return True
        return False