from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoManagerRunRecord


class RepoManagerRunRepository:
    """Persistence operations for repo-manager runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
        run_fingerprint: str,
        prompt_version: str,
    ) -> RepoManagerRunRecord:
        record = RepoManagerRunRecord(
            id=str(uuid4()),
            source_run_id=source_run_id,
            source_file_summary_run_id=source_file_summary_run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="queued",
            error_message=None,
            run_fingerprint=run_fingerprint,
            prompt_version=prompt_version,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, repo_manager_run_id: str) -> RepoManagerRunRecord | None:
        stmt = select(RepoManagerRunRecord).where(RepoManagerRunRecord.id == repo_manager_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoped(
        self,
        repo_manager_run_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> RepoManagerRunRecord | None:
        stmt = select(RepoManagerRunRecord).where(
            RepoManagerRunRecord.id == repo_manager_run_id,
            RepoManagerRunRecord.tenant_id == tenant_id,
            RepoManagerRunRecord.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_in_progress(self, run: RepoManagerRunRecord) -> None:
        run.status = "in_progress"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_completed(self, run: RepoManagerRunRecord) -> None:
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_failed(self, run: RepoManagerRunRecord, *, error_message: str) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        await self.session.flush()

    async def set_counts(
        self,
        run: RepoManagerRunRecord,
        *,
        groups_seen: int,
        groups_summarized: int,
        groups_failed: int,
        members_seen: int,
    ) -> None:
        run.groups_seen = groups_seen
        run.groups_summarized = groups_summarized
        run.groups_failed = groups_failed
        run.members_seen = members_seen
        await self.session.flush()

    async def set_architecture_artifact(
        self,
        run: RepoManagerRunRecord,
        *,
        architecture_overview: str,
        merged_mermaid_diagram: str,
        merge_raw_output: dict,
    ) -> None:
        run.architecture_overview = architecture_overview
        run.merged_mermaid_diagram = merged_mermaid_diagram
        run.merge_raw_output = merge_raw_output
        await self.session.flush()

    async def find_completed_by_fingerprint(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
        run_fingerprint: str,
    ) -> RepoManagerRunRecord | None:
        stmt = (
            select(RepoManagerRunRecord)
            .where(
                RepoManagerRunRecord.source_run_id == source_run_id,
                RepoManagerRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoManagerRunRecord.tenant_id == tenant_id,
                RepoManagerRunRecord.user_id == user_id,
                RepoManagerRunRecord.run_fingerprint == run_fingerprint,
                RepoManagerRunRecord.status == "completed",
            )
            .order_by(desc(RepoManagerRunRecord.finished_at), desc(RepoManagerRunRecord.queued_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def latest_completed_for_source(
        self,
        *,
        source_run_id: str,
        tenant_id: str,
        user_id: str,
    ) -> RepoManagerRunRecord | None:
        stmt = (
            select(RepoManagerRunRecord)
            .where(
                RepoManagerRunRecord.source_run_id == source_run_id,
                RepoManagerRunRecord.tenant_id == tenant_id,
                RepoManagerRunRecord.user_id == user_id,
                RepoManagerRunRecord.status == "completed",
            )
            .order_by(desc(RepoManagerRunRecord.finished_at), desc(RepoManagerRunRecord.queued_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def latest_for_source(
        self,
        *,
        source_run_id: str,
        tenant_id: str,
        user_id: str,
        statuses: list[str] | None = None,
    ) -> RepoManagerRunRecord | None:
        """Return latest repo-manager run for one source run, optionally filtered by status."""

        stmt = (
            select(RepoManagerRunRecord)
            .where(
                RepoManagerRunRecord.source_run_id == source_run_id,
                RepoManagerRunRecord.tenant_id == tenant_id,
                RepoManagerRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoManagerRunRecord.queued_at), desc(RepoManagerRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoManagerRunRecord.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def latest_for_source_file_summary(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
        statuses: list[str] | None = None,
    ) -> RepoManagerRunRecord | None:
        """Return latest repo-manager run for one source+file_summary pair, filtered by status when provided."""

        stmt = (
            select(RepoManagerRunRecord)
            .where(
                RepoManagerRunRecord.source_run_id == source_run_id,
                RepoManagerRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoManagerRunRecord.tenant_id == tenant_id,
                RepoManagerRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoManagerRunRecord.queued_at), desc(RepoManagerRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoManagerRunRecord.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_stale_runs_failed(self) -> int:
        """Mark queued/in-progress repo-manager runs as failed when worker restarts."""
        stmt = select(RepoManagerRunRecord).where(
            RepoManagerRunRecord.status.in_(["queued", "in_progress"])
        )
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0

        now = datetime.now(timezone.utc)
        for run in runs:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "Worker restarted before repo-manager completion"
        await self.session.flush()
        return len(runs)
