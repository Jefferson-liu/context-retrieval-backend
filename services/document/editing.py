from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.repositories import DocumentRepository, ChunkRepository
from services.document.processing import DocumentProcessingService

class DocumentEditingService:
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.document_repository = DocumentRepository(db, context)
        self.document_processing_service = DocumentProcessingService(db, context)
        self.chunk_repository = ChunkRepository(db, context)
        
        
    async def edit_document(self, document_id: int, new_context: str):
        """Edit an existing document."""
        try:
            # Step 1: Update the document context
            db_document = await self.document_repository.edit_document(document_id, context=new_context)
            
            existing_chunk_ids = await self.chunk_repository.get_chunk_ids_by_doc_id(document_id)
            if existing_chunk_ids:
                await self.document_processing_service.vector_store.delete_vectors(
                    existing_chunk_ids,
                    tenant_id=self.context.tenant_id,
                )

            await self.chunk_repository.delete_chunks_by_doc_id(document_id)
            # Step 2: Re-process the document (chunk and embed)
            await self.document_processing_service.process_document(document_id, new_context)
            return db_document
        except Exception as e:
            await self.db.rollback()
            raise e
        