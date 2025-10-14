import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.repositories import DocumentRepository, ChunkRepository
from infrastructure.ai.chunking import Chunker
from infrastructure.ai.embedding import Embedder
from infrastructure.version_control.git_service import GitService
from services.file import DocumentFileService
from infrastructure.vector_store import VectorRecord, create_vector_store
from langchain_anthropic import ChatAnthropic
from config import settings

class DocumentProcessingService:
    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.document_repository = DocumentRepository(db, context)
        self.chunk_repository = ChunkRepository(db, context)
        self.chunker = Chunker()
        self.embedder = Embedder(ChatAnthropic(temperature=0, model_name="claude-3-5-haiku-latest", api_key=settings.ANTHROPIC_API_KEY))
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

        if not chunks:
            return

        parallelism = max(1, min(4, len(chunks)))
        context_sem = asyncio.Semaphore(parallelism)

        async def contextualize(index: int, chunk: dict):
            async with context_sem:
                contextualized = await self.embedder.contextualize_chunk_content(chunk["content"], content)
            return index, chunk, contextualized

        contextualized_chunks = await asyncio.gather(
            *(contextualize(i, chunk) for i, chunk in enumerate(chunks))
        )
        contextualized_chunks.sort(key=lambda item: item[0])

        chunk_objects = []
        for index, chunk_payload, contextualized_chunk in contextualized_chunks:
            chunk_obj = await self.chunk_repository.create_chunk(
                document_id,
                index,
                contextualized_chunk,
                chunk_payload["content"],
            )
            chunk_objects.append(chunk_obj)

        embed_sem = asyncio.Semaphore(parallelism)

        async def build_vector_record(chunk_obj):
            text_parts = [chunk_obj.context, chunk_obj.content]
            text = " ".join(part for part in text_parts if part).strip()
            async with embed_sem:
                embedding = await self.embedder.generate_embedding(text)
            return VectorRecord(
                chunk_id=chunk_obj.id,
                embedding=embedding,
                tenant_id=self.context.tenant_id,
                project_id=chunk_obj.project_id,
            )

        records = await asyncio.gather(*(build_vector_record(chunk_obj) for chunk_obj in chunk_objects))

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

        doc_name = document.doc_name
        document.context = context
        document.content = context
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

        file_path = await self.document_file_service.write_document(document_id, doc_name, context)
        if file_path:
            message = commit_message or f"Update document: {doc_name}"
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
    
