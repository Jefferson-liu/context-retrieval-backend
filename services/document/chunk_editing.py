from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from infrastructure.ai.embedding import Embedder
from infrastructure.ai.chunking import Chunker
from infrastructure.context import ContextScope
from infrastructure.database.repositories import ChunkRepository, DocumentRepository
from infrastructure.vector_store import VectorRecord, create_vector_store
from langchain_anthropic import ChatAnthropic
from infrastructure.database.models.documents import Chunk


class ChunkEditingService:
    """Handles updates to individual document chunks."""

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        *,
        embedder: Optional[Embedder] = None,
        vector_store=None,
    ) -> None:
        self.db = db
        self.context = context
        self.chunk_repository = ChunkRepository(db, context)
        self.document_repository = DocumentRepository(db, context)
        self.embedder = embedder or Embedder(
            ChatAnthropic(
                temperature=0,
                model_name="claude-3-5-sonnet-latest",
                api_key=settings.ANTHROPIC_API_KEY,
            )
        )
        self.vector_store = vector_store or create_vector_store(db)
        self._chunker = Chunker()
        self._chunk_size_hint = max(1, getattr(self._chunker, "chunk_size", 512))
        self._chunk_overlap_hint = max(0, getattr(self._chunker, "overlap_size", 0))

    def _locate_chunk_span(self, document_text: str, chunk: Chunk) -> Optional[tuple[int, int]]:
        """Best-effort locate the position of the chunk inside the parent document text."""
        chunk_text = (chunk.content or "")
        if not chunk_text or not document_text:
            return None

        stride = max(1, self._chunk_size_hint - self._chunk_overlap_hint)
        approx_start = chunk.chunk_order * stride
        search_window_start = max(0, approx_start - self._chunk_size_hint)

        position = document_text.find(chunk_text, search_window_start)
        if position == -1:
            position = document_text.find(chunk_text)
            if position == -1:
                return None

        return position, position + len(chunk_text)

    async def update_chunk(
        self,
        chunk_id: int,
        *,
        content: Optional[str] = None,
    ) -> Optional[Chunk]:
        """Update the chunk and refresh its embedding."""
        chunk = await self.chunk_repository.get_chunk_by_id(chunk_id)
        if not chunk:
            return None
        
        doc_id = chunk.doc_id

        document = await self.document_repository.get_document_by_id(doc_id)
        document_text = document.content

        current_content = chunk.content
        current_context = chunk.context

        new_content = content if content is not None else current_content
        new_context: Optional[str] = "temp context"

        doc_updated = False
        updated_doc_body = document_text
        
        span = self._locate_chunk_span(document_text, chunk)
        if span:
            start, end = span
            updated_doc_body = document_text[:start] + new_content + document_text[end:]
            doc_updated = True
        elif current_content:
            replacement = document_text.replace(current_content, new_content, 1)
            if replacement != document_text:
                updated_doc_body = replacement
                doc_updated = True
        else:
            new_context = current_context

        doc_for_context = updated_doc_body if doc_updated else document_text
        new_context = await self.embedder.contextualize_chunk_content(new_content, doc_for_context)
        
        await self.chunk_repository.edit_chunk(
            chunk_id,
            content=new_content,
            context=new_context,
        )

        text_parts = [part for part in (new_context, new_content) if part]
        if text_parts:
            embedding = await self.embedder.generate_embedding(" ".join(text_parts).strip())
            await self.vector_store.upsert_vectors(
                [
                    VectorRecord(
                        chunk_id=chunk_id,
                        embedding=embedding,
                        tenant_id=chunk.tenant_id,
                        project_id=chunk.project_id,
                    )
                ]
            )
            await self.db.flush()
        else:
            await self.vector_store.delete_vectors(
                [chunk_id],
                tenant_id=chunk.tenant_id,
                project_id=chunk.project_id,
            )
            await self.db.flush()

        if document and doc_updated:
            await self.document_repository.edit_document(
                doc_id,
                content=updated_doc_body,
                context=updated_doc_body,
                doc_size=len(updated_doc_body),
            )

        await self.db.flush()

        return chunk