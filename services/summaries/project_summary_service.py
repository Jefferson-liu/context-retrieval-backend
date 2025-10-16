from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence, List

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from infrastructure.context import ContextScope
from infrastructure.database.models.documents import ProjectSummary
from infrastructure.database.repositories import DocumentRepository, DocumentSummaryRepository
from infrastructure.database.repositories.project_summary_repository import ProjectSummaryRepository


class ProjectSummaryService:
    """Manages the lifecycle of tenant/project-scoped summary aggregates."""

    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        llm: BaseChatModel,
    ):
        self.db = db
        self.context = context
        self.llm = llm
        self.document_repository = DocumentRepository(db, context)
        self.project_summary_repository = ProjectSummaryRepository(db, context)
        self.document_summary_repository = DocumentSummaryRepository(db, context)

    async def upsert_summary(
        self,
        *,
        document_summaries: List[str],
        summary_tokens: Optional[int] = None,
        source_document_ids: Optional[Iterable[int]] = None,
        refreshed_at: Optional[datetime] = None,
    ) -> ProjectSummary:
        """Create or refresh the canonical project summary."""
        effective_refreshed_at = refreshed_at or datetime.utcnow()
        summary_text = await self._generate_project_summary(document_summaries)

        return await self.project_summary_repository.upsert_summary(
            summary_text=summary_text,
            project_id=self.context.primary_project(),
            summary_tokens=summary_tokens,
            source_document_ids=source_document_ids,
            refreshed_at=effective_refreshed_at,
        )

    async def update_summary(self):
        """Refresh the stored project summary to reflect the current context."""
        documents = await self.document_repository.get_all_documents()
        document_ids = [doc.id for doc in documents]
        if not document_ids:
            return None

        summary_rows = await self.document_summary_repository.list_by_document_ids(document_ids)
        document_summaries = [row.summary_text for row in summary_rows if row.summary_text]
        if not document_summaries:
            return None

        existing_summary = await self.get_summary(self.context.primary_project())
        if existing_summary:
            summary_text = await self._generate_updated_summary(existing_summary.summary_text, document_summaries)
        else:
            summary_text = await self._generate_project_summary(document_summaries)

        return await self.project_summary_repository.upsert_summary(
            summary_text=summary_text,
            project_id=self.context.primary_project(),
            summary_tokens=None,
            source_document_ids=document_ids,
            refreshed_at=datetime.utcnow(),
        )

    async def _generate_project_summary(self, document_summaries: List[str]) -> str:
        summaries_text = "\n\n".join(summary.strip() for summary in document_summaries if summary)
        messages: List[BaseMessage] = [
            SystemMessage(
                content=(
                    "You summarize project knowledge using the supplied document summaries. "
                    "Produce a concise overview that captures the key points and central themes."
                )
            ),
            HumanMessage(content=summaries_text),
        ]
        return await self._generate_text(messages)

    async def _generate_updated_summary(self, existing_summary: str, document_summaries: List[str]) -> str:
        summaries_text = "\n\n".join(summary.strip() for summary in document_summaries if summary)
        messages: List[BaseMessage] = [
            SystemMessage(
                content=(
                    "Update the existing project summary with the new document insights. "
                    "Keep the overview concise, prefer confirmed facts from the new summaries, "
                    "and drop outdated information."
                )
            ),
            HumanMessage(
                content=(
                    f"Existing summary:\n{existing_summary}\n\n"
                    f"New document summaries:\n{summaries_text}"
                )
            ),
        ]
        return await self._generate_text(messages)

    async def _generate_text(self, messages: List[BaseMessage]) -> str:
        response = await self.llm.ainvoke(messages)
        if isinstance(response, AIMessage):
            content = response.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: List[str] = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.append(item.get("text", ""))
                return "".join(parts).strip()
        return str(response)

    async def get_summary(self, project_id: Optional[int] = None) -> Optional[ProjectSummary]:
        """Fetch the project summary record."""
        return await self.project_summary_repository.get_by_project_id(project_id)

    async def list_summaries(self, project_ids: Iterable[int]) -> Sequence[ProjectSummary]:
        """Fetch summaries for a set of projects within scope."""
        return await self.project_summary_repository.list_for_projects(project_ids)

    async def delete_summary(self, project_id: Optional[int] = None) -> bool:
        """Remove the stored project summary."""
        return await self.project_summary_repository.delete_by_project_id(project_id)
