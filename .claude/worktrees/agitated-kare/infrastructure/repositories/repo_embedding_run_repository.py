from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoEmbeddingRunRecord


class RepoEmbeddingRunRepository:
    """Persistence operations for repository embedding generation runs."""

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
    ) -> RepoEmbeddingRunRecord:
        record = RepoEmbeddingRunRecord(
            id=str(uuid4()),
            source_run_id=source_run_id,
            source_file_summary_run_id=source_file_summary_run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            status="queued",
            error_message=None,
            run_fingerprint=run_fingerprint,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get(self, embedding_run_id: str) -> RepoEmbeddingRunRecord | None:
        stmt = select(RepoEmbeddingRunRecord).where(RepoEmbeddingRunRecord.id == embedding_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scoped(
        self,
        embedding_run_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> RepoEmbeddingRunRecord | None:
        stmt = select(RepoEmbeddingRunRecord).where(
            RepoEmbeddingRunRecord.id == embedding_run_id,
            RepoEmbeddingRunRecord.tenant_id == tenant_id,
            RepoEmbeddingRunRecord.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_in_progress(self, run: RepoEmbeddingRunRecord) -> None:
        run.status = "in_progress"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_completed(self, run: RepoEmbeddingRunRecord) -> None:
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_failed(self, run: RepoEmbeddingRunRecord, *, error_message: str) -> None:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
        await self.session.flush()

    async def set_counts(
        self,
        run: RepoEmbeddingRunRecord,
        *,
        subjects_seen: int,
        subjects_embedded: int,
        subjects_failed: int,
    ) -> None:
        run.subjects_seen = subjects_seen
        run.subjects_embedded = subjects_embedded
        run.subjects_failed = subjects_failed
        await self.session.flush()

    async def find_completed_by_fingerprint(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str,
        tenant_id: str,
        user_id: str,
        run_fingerprint: str,
    ) -> RepoEmbeddingRunRecord | None:
        stmt = (
            select(RepoEmbeddingRunRecord)
            .where(
                RepoEmbeddingRunRecord.source_run_id == source_run_id,
                RepoEmbeddingRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoEmbeddingRunRecord.tenant_id == tenant_id,
                RepoEmbeddingRunRecord.user_id == user_id,
                RepoEmbeddingRunRecord.run_fingerprint == run_fingerprint,
                RepoEmbeddingRunRecord.status == "completed",
            )
            .order_by(desc(RepoEmbeddingRunRecord.finished_at), desc(RepoEmbeddingRunRecord.queued_at))
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
    ) -> RepoEmbeddingRunRecord | None:
        stmt = (
            select(RepoEmbeddingRunRecord)
            .where(
                RepoEmbeddingRunRecord.source_run_id == source_run_id,
                RepoEmbeddingRunRecord.tenant_id == tenant_id,
                RepoEmbeddingRunRecord.user_id == user_id,
                RepoEmbeddingRunRecord.status == "completed",
            )
            .order_by(desc(RepoEmbeddingRunRecord.finished_at), desc(RepoEmbeddingRunRecord.queued_at))
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
    ) -> RepoEmbeddingRunRecord | None:
        """Return latest embedding run for one source run, optionally filtered by status."""

        stmt = (
            select(RepoEmbeddingRunRecord)
            .where(
                RepoEmbeddingRunRecord.source_run_id == source_run_id,
                RepoEmbeddingRunRecord.tenant_id == tenant_id,
                RepoEmbeddingRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoEmbeddingRunRecord.queued_at), desc(RepoEmbeddingRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoEmbeddingRunRecord.status.in_(statuses))
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
    ) -> RepoEmbeddingRunRecord | None:
        """Return latest embedding run for one source+file_summary pair, optionally filtered by status."""

        stmt = (
            select(RepoEmbeddingRunRecord)
            .where(
                RepoEmbeddingRunRecord.source_run_id == source_run_id,
                RepoEmbeddingRunRecord.source_file_summary_run_id == source_file_summary_run_id,
                RepoEmbeddingRunRecord.tenant_id == tenant_id,
                RepoEmbeddingRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoEmbeddingRunRecord.queued_at), desc(RepoEmbeddingRunRecord.id))
            .limit(1)
        )
        if statuses:
            stmt = stmt.where(RepoEmbeddingRunRecord.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_stale_runs_failed(self) -> int:
        """Mark queued/in-progress embedding runs as failed when worker restarts."""
        stmt = select(RepoEmbeddingRunRecord).where(
            RepoEmbeddingRunRecord.status.in_(["queued", "in_progress"])
        )
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0

        now = datetime.now(timezone.utc)
        for run in runs:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "Worker restarted before embedding completion"
        await self.session.flush()
        return len(runs)
