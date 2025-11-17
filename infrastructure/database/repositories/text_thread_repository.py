from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from infrastructure.context import ContextScope
from infrastructure.database.models.text_threads import TextThread, TextThreadMessage
from infrastructure.database.models.documents import Document
from schemas.requests.text_thread import TextThreadMessageInput


class TextThreadRepository:
    """Repository helpers for text threads."""

    def __init__(self, db: AsyncSession, context: ContextScope) -> None:
        self.db = db
        self.context = context

    async def get_thread_by_source_external(
        self,
        *,
        source_system: str,
        external_thread_id: str,
    ) -> TextThread | None:
        stmt = (
            select(TextThread)
            .where(
                TextThread.tenant_id == self.context.tenant_id,
                TextThread.project_id.in_(self.context.project_ids),
                TextThread.source_system == source_system,
                TextThread.external_thread_id == external_thread_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_thread(
        self,
        owner_user_id: str,
        source_system: str,
        external_thread_id: Optional[str],
        title: Optional[str],
        thread_messages: List[TextThreadMessageInput],
    ) -> TextThread:
        if external_thread_id:
            existing = await self.get_thread_by_source_external(
                source_system=source_system,
                external_thread_id=external_thread_id,
            )
            if existing:
                return existing

        thread = TextThread(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            owner_user_id=owner_user_id,
            user_product_id=None,
            source_system=source_system,
            external_thread_id=external_thread_id,
            title=title,
            thread_text="\n".join(
                msg["text"] for msg in thread_messages if msg["text"]
            ).strip(),
            message_count=0,
        )
        self.db.add(thread)
        await self.db.flush()

        # Also create a document record to map chunks/logical doc for this thread.
        document = Document(
            tenant_id=self.context.tenant_id,
            project_id=self.context.primary_project(),
            doc_name=title or f"Thread {thread.id}",
            doc_type="text/thread",
            content=thread.thread_text,
            doc_size=len(thread.thread_text or ""),
            created_by_user_id=owner_user_id,
        )
        self.db.add(document)
        await self.db.flush()
        thread.document_id = document.id  # type: ignore[attr-defined]

        return thread


__all__ = ["TextThreadRepository"]
