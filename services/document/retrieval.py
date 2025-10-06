from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.repositories import DocumentRepository, ChunkRepository


class DocumentRetrievalService:
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.document_repository = DocumentRepository(db, context)
        self.chunk_repository = ChunkRepository(db, context)

    async def list_documents(self):
        return await self.document_repository.get_all_documents()

    async def get_document(self, document_id: int):
        return await self.document_repository.get_document_by_id(document_id)
    
    async def get_document_chunks(self, document_id: int):
        return await self.chunk_repository.get_chunks_by_doc_id(document_id)
