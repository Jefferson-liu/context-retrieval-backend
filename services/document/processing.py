from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.context import ContextScope
from infrastructure.database.repositories import DocumentRepository, QueryRepository, ChunkRepository
from infrastructure.ai.chunking import Chunker
from infrastructure.ai.embedding import Embedder
from infrastructure.version_control.git_service import GitService
from services.file import DocumentFileService
from infrastructure.vector_store import VectorRecord, create_vector_store

class DocumentProcessingService:
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.document_repository = DocumentRepository(db, context)
        self.chunk_repository = ChunkRepository(db, context)
        self.query_repository = QueryRepository(db, context)
        self.chunker = Chunker()
        self.embedder = Embedder()
        self.git_service = GitService()
        self.document_file_service = DocumentFileService()
        self.vector_store = create_vector_store(db)
        
        
    async def upload_and_process_document(
        self,
        content: str,
        doc_name: str,
        doc_type: str,
        commit_message: str | None = None,
    ):
        """Upload and fully process a document (save, chunk, embed)."""
        # Step 1: Save the document
        db_document = await self.document_repository.create_document(
            doc_name=doc_name, content=content, doc_size=len(content), doc_type=doc_type
        )

        doc_id = db_document.id

        # Step 2: Process the document (chunk and embed)
        await self.process_document(doc_id, content)

        file_path = await self.document_file_service.write_document(doc_id, doc_name, content)
        if file_path:
            message = commit_message or f"Upload document: {doc_name}"
            await self.git_service.commit_changes(message=message, added_paths=[file_path])

        # FastAPI will automatically commit the transaction on successful response
        return doc_id

    async def process_document(self, document_id: int, content: str):
        """Process a document: create chunks and embeddings."""
        # Chunk the content
        chunks = await self.chunker.chunk_text(content)
        chunk_objects = []
        for i, chunk in enumerate(chunks):
            # Create a chunk record in the database
            contextualized_chunk = await self.embedder.contextualize_chunk_content(chunk["content"], content)
            chunk_obj = await self.chunk_repository.create_chunk(document_id, i, contextualized_chunk, chunk["content"])
            chunk_objects.append(chunk_obj)

        # Generate embeddings for each chunk
        records = []
        for chunk_obj in chunk_objects:
            embedding = await self.embedder.generate_embedding(chunk_obj.context + " " + chunk_obj.content)
            records.append(
                VectorRecord(
                    chunk_id=chunk_obj.id,
                    embedding=embedding,
                    tenant_id=self.context.tenant_id,
                    project_id=chunk_obj.project_id,
                )
            )

        await self.vector_store.upsert_vectors(records)

    async def update_document(
        self,
        document_id: int,
        context: str,
        doc_type: str | None = None,
        commit_message: str | None = None,
    ) -> bool:
        document = await self.document_repository.get_document_by_id(document_id)
        if not document:
            return False

        document.context = context
        document.doc_size = len(context)
        if doc_type:
            document.doc_type = doc_type

        await self.db.flush()

        old_chunk_ids = await self.chunk_repository.get_chunk_ids_by_doc_id(document_id)
        if old_chunk_ids:
            await self.vector_store.delete_vectors(
                old_chunk_ids,
                tenant_id=self.context.tenant_id,
            )
        await self.chunk_repository.delete_chunks_by_doc_id(document_id)
        await self.process_document(document_id, context)

        file_path = await self.document_file_service.write_document(document_id, document.doc_name, context)
        if file_path:
            message = commit_message or f"Update document: {document.doc_name}"
            await self.git_service.commit_changes(message=message, added_paths=[file_path])
        return True

    async def delete_document(self, document_id: int, commit_message: str | None = None):
        document = await self.document_repository.get_document_by_id(document_id)
        if not document:
            return False

        existing_chunk_ids = await self.chunk_repository.get_chunk_ids_by_doc_id(document_id)
        if existing_chunk_ids:
            await self.vector_store.delete_vectors(
                existing_chunk_ids,
                tenant_id=self.context.tenant_id,
            )

        success = await self.document_repository.delete_document(document_id)
        if success:
            file_path = await self.document_file_service.delete_document(document_id, document.doc_name)
            if file_path:
                message = commit_message or f"Delete document: {document.doc_name}"
                await self.git_service.commit_changes(message=message, removed_paths=[file_path])
        return success
    
    async def list_documents(self):
        return await self.document_repository.get_all_documents()
    
    async def get_document(self, document_id: int):
        return await self.document_repository.get_document_by_id(document_id)