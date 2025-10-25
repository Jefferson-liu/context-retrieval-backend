from __future__ import annotations

from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.documents import DocumentSummary, Document


class DocumentSummaryRepository:
    """Persistence gateway for tenant/project-scoped document summaries."""

    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context

    async def upsert_summary(
        self,
        *,
        document_id: int,
        summary_text: str,
        summary_tokens: Optional[int] = None,
        summary_hash: Optional[str] = None,
        milvus_primary_key: Optional[int] = None,
    ) -> DocumentSummary:
        """Create or update the summary associated with a document."""
        summary = await self.get_by_document_id(document_id)
        if summary:
            summary.summary_text = summary_text
            summary.summary_tokens = summary_tokens
            summary.summary_hash = summary_hash
            summary.milvus_primary_key = milvus_primary_key
        else:
            summary = DocumentSummary(
                tenant_id=self.context.tenant_id,
                project_id=self.context.primary_project(),
                document_id=document_id,
                summary_text=summary_text,
                summary_tokens=summary_tokens,
                summary_hash=summary_hash,
                milvus_primary_key=milvus_primary_key,
            )
            self.db.add(summary)

        await self.db.flush()
        return summary

    async def get_by_document_id(self, document_id: int) -> Optional[DocumentSummary]:
        """Fetch the summary for a document constrained to the current scope."""
        stmt = (
            select(DocumentSummary)
            .join(Document, Document.id == DocumentSummary.document_id)
            .where(
                DocumentSummary.document_id == document_id,
                DocumentSummary.tenant_id == self.context.tenant_id,
                DocumentSummary.project_id.in_(self.context.project_ids),
                Document.created_by_user_id == self.context.user_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_document_ids(self, document_ids: Iterable[int]) -> Sequence[DocumentSummary]:
        """Return summaries for the provided document ids within the current scope."""
        ids = list(document_ids)
        if not ids:
            return []

        stmt = (
            select(DocumentSummary)
            .join(Document, Document.id == DocumentSummary.document_id)
            .where(
                DocumentSummary.document_id.in_(ids),
                DocumentSummary.tenant_id == self.context.tenant_id,
                DocumentSummary.project_id.in_(self.context.project_ids),
                Document.created_by_user_id == self.context.user_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_by_document_id(self, document_id: int) -> bool:
        """Remove a document summary if it exists within the current scope."""
        summary = await self.get_by_document_id(document_id)
        if summary is None:
            return False

        await self.db.delete(summary)
        await self.db.flush()
        return True
