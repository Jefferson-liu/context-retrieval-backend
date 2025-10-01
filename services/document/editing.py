from sqlalchemy.orm import Session
from infrastructure.database.repositories import DocumentRepository, SearchRepository, QueryRepository, ChunkRepository
from infrastructure.ai.chunking import Chunker
from infrastructure.ai.embedding import Embedder
from services.document.processing import DocumentProcessingService

class DocumentEditingService:
    def __init__(self, db: Session):
        self.db = db
        self.document_repository = DocumentRepository(db)
        self.document_processing_service = DocumentProcessingService(db)
        self.search_repository = SearchRepository(db)
        self.chunk_repository = ChunkRepository(db)
        self.query_repository = QueryRepository(db)
        self.chunker = Chunker()
        self.embedder = Embedder()
        
        
    async def edit_document(self, document_id: int, new_content: str):
        """Edit an existing document."""
        try:
            # Step 1: Update the document content
            db_document = self.document_repository.edit_document(document_id, content=new_content)
            if not db_document:
                raise ValueError(f"Document with ID {document_id} not found.")
            
            await self.chunk_repository.delete_chunks_by_doc_id(document_id)
            # Step 2: Re-process the document (chunk and embed)
            await self.document_processing_service.process_document(document_id, new_content)
            await self.db.commit()
            return db_document
        except Exception as e:
            self.db.rollback()
            raise e
        