from sqlalchemy.orm import Session
from infrastructure.database.repositories import DocumentRepository, SearchRepository, QueryRepository, ChunkRepository
from infrastructure.ai.chunking import Chunker
from infrastructure.ai.embedding import Embedder

class DocumentProcessingService:
    def __init__(self, db: Session):
        self.db = db
        self.document_repository = DocumentRepository(db)
        self.search_repository = SearchRepository(db)
        self.chunk_repository = ChunkRepository(db)
        self.query_repository = QueryRepository(db)
        self.chunker = Chunker()
        self.embedder = Embedder()
        
        
    async def upload_and_process_document(self, content: str, doc_name: str, doc_type: str):
        """Upload and fully process a document (save, chunk, embed)."""
        # Step 1: Save the document
        db_document = self.document_repository.create_document(
            doc_name=doc_name, content=content, doc_size=len(content), doc_type=doc_type
        )
        
        # Step 2: Process the document (chunk and embed)
        await self.process_document(db_document.id, content)
        
        await self.db.commit()
        return db_document

    async def process_document(self, document_id: int, content: str):
        """Process a document: create chunks and embeddings."""
        # Chunk the content
        chunks = await self.chunker.chunk_text(content)
        for i, chunk in enumerate(chunks):
            # Create a chunk record in the database
            contextualized_chunk = await self.embedder.contextualize_chunk_content(chunk)
            self.chunk_repository.create_chunk(document_id, i, contextualized_chunk, content)
        # Generate embeddings for each chunk
        for chunk in chunks:
            embedding = await self.embedder.generate_embedding(chunk)
            self.chunk_repository.create_embedding(chunk.id, embedding)

    def delete_document(self, document_id: int):
        success = self.document_repository.delete_document(document_id)
        if success:
            self.db.commit()
        return success