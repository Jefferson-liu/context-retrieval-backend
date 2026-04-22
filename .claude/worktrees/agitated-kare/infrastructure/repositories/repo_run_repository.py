from __future__ import annotations

from datetime import datetime, timezone
import logging
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoRunRecord

logger = logging.getLogger(__name__)


class RepoRunRepository:
    """Persistence operations for repository ingestion runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        tenant_id: str,
        user_id: str,
        source_type: str,
        source_locator: str,
        repo_address: str,
        include_extensions: str | None,
        exclude_globs: str | None,
    ) -> RepoRunRecord:
        run = RepoRunRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            source_type=source_type,
            source_locator=source_locator,
            repo_address=repo_address,
            include_extensions=include_extensions,
            exclude_globs=exclude_globs,
            status="queued",
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_scoped(self, run_id: str, *, tenant_id: str, user_id: str) -> RepoRunRecord | None:
        stmt = (
            select(RepoRunRecord)
            .where(
                RepoRunRecord.id == run_id,
                RepoRunRecord.tenant_id == tenant_id,
                RepoRunRecord.user_id == user_id,
            )
            .order_by(RepoRunRecord.queued_at.asc(), RepoRunRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate scoped repo runs detected run_id=%s tenant_id=%s user_id=%s count=%s",
                run_id,
                tenant_id,
                user_id,
                len(rows),
            )
        return rows[0] if rows else None

    async def get(self, run_id: str) -> RepoRunRecord | None:
        stmt = (
            select(RepoRunRecord)
            .where(RepoRunRecord.id == run_id)
            .order_by(RepoRunRecord.queued_at.asc(), RepoRunRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning("Duplicate repo runs detected run_id=%s count=%s", run_id, len(rows))
        return rows[0] if rows else None

    async def list_scoped(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
    ) -> list[RepoRunRecord]:
        stmt = (
            select(RepoRunRecord)
            .where(
                RepoRunRecord.tenant_id == tenant_id,
                RepoRunRecord.user_id == user_id,
            )
            .order_by(desc(RepoRunRecord.queued_at), desc(RepoRunRecord.id))
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(RepoRunRecord.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_in_progress(self, run: RepoRunRecord) -> None:
        run.status = "in_progress"
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_completed(self, run: RepoRunRecord, *, fingerprint: str) -> None:
        run.status = "completed"
        run.fingerprint = fingerprint
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_skipped_duplicate(self, run: RepoRunRecord, *, fingerprint: str) -> None:
        run.status = "skipped_duplicate"
        run.fingerprint = fingerprint
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()

    async def mark_failed(self, run: RepoRunRecord, *, error_message: str) -> None:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def set_counts(
        self,
        run: RepoRunRecord,
        *,
        files_seen: int,
        files_ingested: int,
        files_skipped: int,
        chunks_written: int,
        parse_success_count: int,
        parse_failed_count: int,
        edge_count_file: int,
        edge_count_symbol: int,
    ) -> None:
        run.files_seen = files_seen
        run.files_ingested = files_ingested
        run.files_skipped = files_skipped
        run.chunks_written = chunks_written
        run.parse_success_count = parse_success_count
        run.parse_failed_count = parse_failed_count
        run.edge_count_file = edge_count_file
        run.edge_count_symbol = edge_count_symbol
        await self.session.flush()

    async def find_completed_by_fingerprint(
        self,
        *,
        tenant_id: str,
        user_id: str,
        source_locator: str,
        fingerprint: str,
        excluding_run_id: str,
    ) -> RepoRunRecord | None:
        stmt = (
            select(RepoRunRecord)
            .where(
                RepoRunRecord.tenant_id == tenant_id,
                RepoRunRecord.user_id == user_id,
                RepoRunRecord.source_locator == source_locator,
                RepoRunRecord.fingerprint == fingerprint,
                RepoRunRecord.status.in_(["completed", "skipped_duplicate"]),
                RepoRunRecord.id != excluding_run_id,
            )
            .order_by(desc(RepoRunRecord.finished_at), desc(RepoRunRecord.queued_at), desc(RepoRunRecord.id))
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Multiple duplicate-candidate runs found tenant_id=%s user_id=%s source_locator=%s fingerprint=%s count=%s",
                tenant_id,
                user_id,
                source_locator,
                fingerprint,
                len(rows),
            )
        return rows[0] if rows else None

    async def mark_stale_runs_failed(self) -> int:
        """Mark queued/in-progress runs as failed when worker restarts."""
        stmt = select(RepoRunRecord).where(RepoRunRecord.status.in_(["queued", "in_progress"]))
        result = await self.session.execute(stmt)
        runs = list(result.scalars().all())
        if not runs:
            return 0
        now = datetime.now(timezone.utc)
        for run in runs:
            run.status = "failed"
            run.finished_at = now
            run.error_message = "Worker restarted before run completion"
        await self.session.flush()
        return len(runs)
