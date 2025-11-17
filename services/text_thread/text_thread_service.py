from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.repositories.text_thread_repository import TextThreadRepository
from services.knowledge import KnowledgeGraphService

logger = logging.getLogger(__name__)


class TextThreadService:
    """Service to store text threads and run knowledge extraction."""

    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context
        self.thread_repository = TextThreadRepository(db, context)
        self.knowledge_service = KnowledgeGraphService(db, context)

    async def upload_text_thread(
        self,
        title: str | None,
        source_system: str = "manual",
        external_thread_id: str | None = None,
        messages: list | None = None,
    ):
        parts: list[str] = []
        if messages:
            for msg in messages:
                text_part = None
                if isinstance(msg, dict):
                    text_part = msg.get("text") or msg.get("content") or msg.get("message")
                else:
                    text_part = (
                        getattr(msg, "text", None)
                        or getattr(msg, "content", None)
                        or getattr(msg, "message", None)
                    )
                if text_part:
                    parts.append(str(text_part))
                elif msg:
                    parts.append(str(msg))

        thread_text = "\n".join(parts).strip()
        if not thread_text:
            raise ValueError("Thread content is empty; provide messages with text.")

        thread = await self.thread_repository.create_thread(
            owner_user_id=self.context.user_id,
            source_system=source_system,
            external_thread_id=external_thread_id,
            title=title,
            thread_text=thread_text,
        )
        knowledge_result = await self.knowledge_service.refresh_text_thread_knowledge(
            thread_id=thread.id,
            thread_title=thread.title,
            thread_text=thread.thread_text,
        )
        return {"thread_id": thread.id, "knowledge_result": knowledge_result}
