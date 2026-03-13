from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFullSummaryRunRecord


class RepoFullSummaryRunRepository:
    """Persistence operations for repository full-summary (README) runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
        model_provider: str,
        model_name: str,
        prompt_version: str,
        run_fingerprint: str,
    ) -> RepoFullSummaryRunRecord:
        record = RepoFullSummaryRunRecord(
            id=str(uuid4()),
            source_run_id=source_run_id,
            source_file_summary_run_id=source_file_summary_run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="queued",
            error_message=None,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
            run_fingerprint=run_fingerprint,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, repo_full_summary_run_id: str) -> RepoFullSummaryRunRecord | None:
        stmt = select(RepoFullSummaryRunRecord).where(RepoFullSummaryRunRecord.id == repo_full_summary_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoped(
        self,
        repo_full_summary_run_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> RepoFullSummaryRunRecord | None:
        stmt = select(RepoFullSummaryRunRecord).where(
            RepoFullSummaryRunRecord.id == repo_full_summary_run_id,
            RepoFullSummaryRunRecord.tenant_id == tenant_id,
            RepoFullSummaryRunRecord.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_in_progress(self, run: RepoFullSummaryRunRecord) -> None:
        run.status = "in_progress"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_completed(self, run: RepoFullSummaryRunRecord) -> None:
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_failed(self, run: RepoFullSummaryRunRecord, *, error_message: str) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        await self.session.flush()

    async def set_counts(
        self,
        run: RepoFullSummaryRunRecord,
        *,
        files_seen: int,
        files_used: int,
    ) -> None:
        run.files_seen = files_seen
        run.files_used = files_used
        await self.session.flush()

    async def find_completed_by_fingerprint(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
        run_fingerprint: str,
    ) -> RepoFullSummaryRunRecord | None:
        stmt = (
            select(RepoFullSummaryRunRecord)
            .where(
                RepoFullSummaryRunRecord.source_run_id == source_run_id,
                RepoFullSummaryRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoFullSummaryRunRecord.tenant_id == tenant_id,
                RepoFullSummaryRunRecord.user_id == user_id,
                RepoFullSummaryRunRecord.run_fingerprint == run_fingerprint,
                RepoFullSummaryRunRecord.status == "completed",
            )
            .order_by(desc(RepoFullSummaryRunRecord.finished_at), desc(RepoFullSummaryRunRecord.queued_at))
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
    ) -> RepoFullSummaryRunRecord | None:
        stmt = (
            select(RepoFullSummaryRunRecord)
            .where(
                RepoFullSummaryRunRecord.source_run_id == source_run_id,
                RepoFullSummaryRunRecord.tenant_id == tenant_id,
                RepoFullSummaryRunRecord.user_id == user_id,
                RepoFullSummaryRunRecord.status == "completed",
            )
            .order_by(desc(RepoFullSummaryRunRecord.finished_at), desc(RepoFullSummaryRunRecord.queued_at))
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
    ) -> RepoFullSummaryRunRecord | None:
        stmt = (
            select(RepoFullSummaryRunRecord)
            .where(
                RepoFullSummaryRunRecord.source_run_id == source_run_id,
                RepoFullSummaryRunRecord.tenant_id == tenant_id,
                RepoFullSummaryRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoFullSummaryRunRecord.queued_at), desc(RepoFullSummaryRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoFullSummaryRunRecord.status.in_(statuses))
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
    ) -> RepoFullSummaryRunRecord | None:
        stmt = (
            select(RepoFullSummaryRunRecord)
            .where(
                RepoFullSummaryRunRecord.source_run_id == source_run_id,
                RepoFullSummaryRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoFullSummaryRunRecord.tenant_id == tenant_id,
                RepoFullSummaryRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoFullSummaryRunRecord.queued_at), desc(RepoFullSummaryRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoFullSummaryRunRecord.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_stale_runs_failed(self) -> int:
        """Mark queued/in-progress repo-full-summary runs as failed on worker restart."""

        stmt = select(RepoFullSummaryRunRecord).where(
            RepoFullSummaryRunRecord.status.in_(["queued", "in_progress"])
        )
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0

        now = datetime.now(timezone.utc)
        for run in runs:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "Worker restarted before repo-full-summary completion"
        await self.session.flush()
        return len(runs)
