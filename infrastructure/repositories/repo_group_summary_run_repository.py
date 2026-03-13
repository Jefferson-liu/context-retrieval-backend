from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoGroupSummaryRunRecord


class RepoGroupSummaryRunRepository:
    """Persistence operations for repository group-summary runs."""

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
    ) -> RepoGroupSummaryRunRecord:
        record = RepoGroupSummaryRunRecord(
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

    async def get(self, group_summary_run_id: str) -> RepoGroupSummaryRunRecord | None:
        stmt = select(RepoGroupSummaryRunRecord).where(RepoGroupSummaryRunRecord.id == group_summary_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoped(
        self,
        group_summary_run_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> RepoGroupSummaryRunRecord | None:
        stmt = select(RepoGroupSummaryRunRecord).where(
            RepoGroupSummaryRunRecord.id == group_summary_run_id,
            RepoGroupSummaryRunRecord.tenant_id == tenant_id,
            RepoGroupSummaryRunRecord.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_in_progress(self, run: RepoGroupSummaryRunRecord) -> None:
        run.status = "in_progress"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_completed(self, run: RepoGroupSummaryRunRecord) -> None:
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_failed(self, run: RepoGroupSummaryRunRecord, *, error_message: str) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        await self.session.flush()

    async def set_counts(
        self,
        run: RepoGroupSummaryRunRecord,
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
        run: RepoGroupSummaryRunRecord,
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
    ) -> RepoGroupSummaryRunRecord | None:
        stmt = (
            select(RepoGroupSummaryRunRecord)
            .where(
                RepoGroupSummaryRunRecord.source_run_id == source_run_id,
                RepoGroupSummaryRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoGroupSummaryRunRecord.tenant_id == tenant_id,
                RepoGroupSummaryRunRecord.user_id == user_id,
                RepoGroupSummaryRunRecord.run_fingerprint == run_fingerprint,
                RepoGroupSummaryRunRecord.status == "completed",
            )
            .order_by(desc(RepoGroupSummaryRunRecord.finished_at), desc(RepoGroupSummaryRunRecord.queued_at))
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
    ) -> RepoGroupSummaryRunRecord | None:
        stmt = (
            select(RepoGroupSummaryRunRecord)
            .where(
                RepoGroupSummaryRunRecord.source_run_id == source_run_id,
                RepoGroupSummaryRunRecord.tenant_id == tenant_id,
                RepoGroupSummaryRunRecord.user_id == user_id,
                RepoGroupSummaryRunRecord.status == "completed",
            )
            .order_by(desc(RepoGroupSummaryRunRecord.finished_at), desc(RepoGroupSummaryRunRecord.queued_at))
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
    ) -> RepoGroupSummaryRunRecord | None:
        """Return latest group-summary run for one source run, optionally filtered by status."""

        stmt = (
            select(RepoGroupSummaryRunRecord)
            .where(
                RepoGroupSummaryRunRecord.source_run_id == source_run_id,
                RepoGroupSummaryRunRecord.tenant_id == tenant_id,
                RepoGroupSummaryRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoGroupSummaryRunRecord.queued_at), desc(RepoGroupSummaryRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoGroupSummaryRunRecord.status.in_(statuses))
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
    ) -> RepoGroupSummaryRunRecord | None:
        """Return latest group-summary run for one source+file_summary pair, filtered by status when provided."""

        stmt = (
            select(RepoGroupSummaryRunRecord)
            .where(
                RepoGroupSummaryRunRecord.source_run_id == source_run_id,
                RepoGroupSummaryRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoGroupSummaryRunRecord.tenant_id == tenant_id,
                RepoGroupSummaryRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoGroupSummaryRunRecord.queued_at), desc(RepoGroupSummaryRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoGroupSummaryRunRecord.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_stale_runs_failed(self) -> int:
        """Mark queued/in-progress group-summary runs as failed when worker restarts."""
        stmt = select(RepoGroupSummaryRunRecord).where(
            RepoGroupSummaryRunRecord.status.in_(["queued", "in_progress"])
        )
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0

        now = datetime.now(timezone.utc)
        for run in runs:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "Worker restarted before group-summary completion"
        await self.session.flush()
        return len(runs)
