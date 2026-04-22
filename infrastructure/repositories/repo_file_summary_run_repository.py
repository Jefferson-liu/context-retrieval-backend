from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFileSummaryRunRecord


class RepoFileSummaryRunRepository:
    """Persistence operations for repository summary file_summary runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        source_run_id: str,
        tenant_id: str,
        user_id: str,
        model_provider: str,
        model_name: str,
        prompt_version: str,
        run_fingerprint: str,
    ) -> RepoFileSummaryRunRecord:
        record = RepoFileSummaryRunRecord(
            id=str(uuid4()),
            source_run_id=source_run_id,
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

    async def get(self, file_summary_run_id: str) -> RepoFileSummaryRunRecord | None:
        stmt = select(RepoFileSummaryRunRecord).where(RepoFileSummaryRunRecord.id == file_summary_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoped(
        self,
        file_summary_run_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> RepoFileSummaryRunRecord | None:
        stmt = select(RepoFileSummaryRunRecord).where(
            RepoFileSummaryRunRecord.id == file_summary_run_id,
            RepoFileSummaryRunRecord.tenant_id == tenant_id,
            RepoFileSummaryRunRecord.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_in_progress(self, run: RepoFileSummaryRunRecord) -> None:
        run.status = "in_progress"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_completed(self, run: RepoFileSummaryRunRecord) -> None:
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_failed(self, run: RepoFileSummaryRunRecord, *, error_message: str) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        await self.session.flush()

    async def set_counts(
        self,
        run: RepoFileSummaryRunRecord,
        *,
        files_seen: int,
        files_summarized: int,
        files_failed: int,
    ) -> None:
        run.files_seen = files_seen
        run.files_summarized = files_summarized
        run.files_failed = files_failed
        await self.session.flush()

    async def find_completed_by_fingerprint(
        self,
        *,
        source_run_id: str,
        tenant_id: str,
        user_id: str,
        run_fingerprint: str,
    ) -> RepoFileSummaryRunRecord | None:
        stmt = (
            select(RepoFileSummaryRunRecord)
            .where(
                RepoFileSummaryRunRecord.source_run_id == source_run_id,
                RepoFileSummaryRunRecord.tenant_id == tenant_id,
                RepoFileSummaryRunRecord.user_id == user_id,
                RepoFileSummaryRunRecord.run_fingerprint == run_fingerprint,
                RepoFileSummaryRunRecord.status == "completed",
            )
            .order_by(desc(RepoFileSummaryRunRecord.finished_at), desc(RepoFileSummaryRunRecord.queued_at))
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
    ) -> RepoFileSummaryRunRecord | None:
        stmt = (
            select(RepoFileSummaryRunRecord)
            .where(
                RepoFileSummaryRunRecord.source_run_id == source_run_id,
                RepoFileSummaryRunRecord.tenant_id == tenant_id,
                RepoFileSummaryRunRecord.user_id == user_id,
                RepoFileSummaryRunRecord.status == "completed",
            )
            .order_by(desc(RepoFileSummaryRunRecord.finished_at), desc(RepoFileSummaryRunRecord.queued_at))
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
    ) -> RepoFileSummaryRunRecord | None:
        """Return latest file_summary run for a source run, optionally filtered by status."""

        stmt = (
            select(RepoFileSummaryRunRecord)
            .where(
                RepoFileSummaryRunRecord.source_run_id == source_run_id,
                RepoFileSummaryRunRecord.tenant_id == tenant_id,
                RepoFileSummaryRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoFileSummaryRunRecord.queued_at), desc(RepoFileSummaryRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoFileSummaryRunRecord.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_sources(
        self,
        *,
        source_run_ids: list[str],
        tenant_id: str,
        user_id: str,
        limit_per_source: int = 10,
    ) -> dict[str, list[RepoFileSummaryRunRecord]]:
        """Return recent file_summary runs grouped by source run id."""
        if not source_run_ids:
            return {}
        stmt = (
            select(RepoFileSummaryRunRecord)
            .where(
                RepoFileSummaryRunRecord.source_run_id.in_(source_run_ids),
                RepoFileSummaryRunRecord.tenant_id == tenant_id,
                RepoFileSummaryRunRecord.user_id == user_id,
            )
            .order_by(
                RepoFileSummaryRunRecord.source_run_id,
                desc(RepoFileSummaryRunRecord.queued_at),
                desc(RepoFileSummaryRunRecord.id),
            )
        )
        result = await self.session.execute(stmt)
        grouped: dict[str, list[RepoFileSummaryRunRecord]] = {source_run_id: [] for source_run_id in source_run_ids}
        for row in result.scalars().all():
            bucket = grouped.setdefault(row.source_run_id, [])
            if len(bucket) >= max(1, limit_per_source):
                continue
            bucket.append(row)
        return grouped

    async def mark_stale_runs_failed(self) -> int:
        """Mark queued/in-progress file_summary runs as failed when worker restarts."""
        stmt = select(RepoFileSummaryRunRecord).where(
            RepoFileSummaryRunRecord.status.in_(["queued", "in_progress"])
        )
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0
        now = datetime.now(timezone.utc)
        for run in runs:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "Worker restarted before file_summary completion"
        await self.session.flush()
        return len(runs)
