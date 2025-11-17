from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.repositories.text_thread_repository import TextThreadRepository
from infrastructure.database.repositories.chunk_repository import ChunkRepository
from infrastructure.ai.chunking import Chunker
from services.knowledge import KnowledgeGraphService

logger = logging.getLogger(__name__)


class TextThreadService:
    """Service to store text threads and run knowledge extraction."""

    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.thread_repository = TextThreadRepository(db, context)
        self.knowledge_service = KnowledgeGraphService(db, context)
        self.chunker = Chunker()
        self.chunk_repository = ChunkRepository(db, context)

    async def upload_text_thread(
        self,
        title: str | None,
        source_system: str = "manual",
        external_thread_id: str | None = None,
        messages: list | None = None,
    ):
        parts: list[str] = []
        # we are storing the actual messages as json lines in the thread content, not just the text
        if messages:
            for msg in messages:
                parts.append(json.dumps(msg))

        thread_text = "\n".join(parts)
        if not thread_text:
            raise ValueError("Thread content is empty; provide messages with text.")

        thread = await self.thread_repository.create_thread(
            owner_user_id=self.context.user_id,
            source_system=source_system,
            external_thread_id=external_thread_id,
            title=title,
            thread_messages=messages,
        )
        # Persist chunks tied to the created document record for this thread.
        doc_id = getattr(thread, "document_id", None)
        if doc_id is None:
            raise ValueError("Thread document was not created; cannot persist chunks.")

        chunks = await self.chunker.chunk_text(thread_text, filename=f"thread_{thread.id}")
        for order, chunk in enumerate(chunks):
            await self.chunk_repository.create_chunk(
                doc_id=doc_id,
                chunk_order=order,
                context_text="Text thread conversation between users",
                content=chunk["content"],
            )

        knowledge_result = await self.knowledge_service.refresh_text_thread_knowledge(
            thread_id=doc_id,
            thread_title=thread.title,
            thread_messages=messages,
        )
        return {"thread_id": thread.id, "knowledge_result": knowledge_result}
