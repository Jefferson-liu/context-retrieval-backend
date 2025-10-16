from __future__ import annotations

from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.documents import ProjectSummary


class ProjectSummaryRepository:
    """Persistence gateway for project-level summaries."""

    def __init__(self, db: AsyncSession, context: ContextScope):
        self.db = db
        self.context = context

    async def upsert_summary(
        self,
        *,
        summary_text: str,
        project_id: Optional[int] = None,
        summary_tokens: Optional[int] = None,
        source_document_ids: Optional[Iterable[int]] = None,
        refreshed_at=None,
    ) -> ProjectSummary:
        """Create or update the summary associated with a project."""
        target_project_id = project_id or self.context.primary_project()
        summary = await self.get_by_project_id(target_project_id)
        normalized_source_ids = list(source_document_ids) if source_document_ids is not None else None

        if summary:
            summary.summary_text = summary_text
            summary.summary_tokens = summary_tokens
            summary.source_document_ids = normalized_source_ids
            summary.refreshed_at = refreshed_at
        else:
            summary = ProjectSummary(
                tenant_id=self.context.tenant_id,
                project_id=target_project_id,
                summary_text=summary_text,
                summary_tokens=summary_tokens,
                source_document_ids=normalized_source_ids,
                refreshed_at=refreshed_at,
            )
            self.db.add(summary)

        await self.db.flush()
        return summary

    async def get_by_project_id(self, project_id: Optional[int] = None) -> Optional[ProjectSummary]:
        """Fetch the project summary for a given project within scope."""
        target_project_id = project_id or self.context.primary_project()
        stmt = select(ProjectSummary).where(
            ProjectSummary.project_id == target_project_id,
            ProjectSummary.tenant_id == self.context.tenant_id,
            ProjectSummary.project_id.in_(self.context.project_ids),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_projects(self, project_ids: Iterable[int]) -> Sequence[ProjectSummary]:
        """Return summaries for a collection of project ids in scope."""
        ids = [pid for pid in project_ids if pid in self.context.project_ids]
        if not ids:
            return []

        stmt = select(ProjectSummary).where(
            ProjectSummary.project_id.in_(ids),
            ProjectSummary.tenant_id == self.context.tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete_by_project_id(self, project_id: Optional[int] = None) -> bool:
        """Remove the project summary if it exists within scope."""
        summary = await self.get_by_project_id(project_id)
        if summary is None:
            return False

        await self.db.delete(summary)
        await self.db.flush()
        return True
