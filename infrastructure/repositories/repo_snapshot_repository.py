from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFileSnapshotRecord, RepoSubjectRecord

logger = logging.getLogger(__name__)


class RepoSnapshotRepository:
    """Persistence for run-scoped file snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        run_id: str,
        subject_id: str,
        size_bytes: int | None,
        line_count: int | None,
        content_hash: str | None,
        encoding: str | None,
        ingest_status: str,
        parse_status: str,
        skip_reason: str | None,
        parse_error: str | None,
        chunk_count: int,
    ) -> RepoFileSnapshotRecord:
        stmt = select(RepoFileSnapshotRecord).where(
            RepoFileSnapshotRecord.run_id == run_id,
            RepoFileSnapshotRecord.subject_id == subject_id,
        ).order_by(RepoFileSnapshotRecord.created_at.asc()).limit(2)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate file snapshots detected run_id=%s subject_id=%s count=%s",
                run_id,
                subject_id,
                len(rows),
            )
        record = rows[0] if rows else None
        if record is None:
            record = RepoFileSnapshotRecord(run_id=run_id, subject_id=subject_id)
            self.session.add(record)

        record.size_bytes = size_bytes
        record.line_count = line_count
        record.content_hash = content_hash
        record.encoding = encoding
        record.ingest_status = ingest_status
        record.parse_status = parse_status
        record.skip_reason = skip_reason
        record.parse_error = parse_error
        record.chunk_count = chunk_count
        await self.session.flush()
        return record

    async def list_for_run(
        self,
        *,
        run_id: str,
        limit: int,
        offset: int,
        ingest_status: str | None = None,
    ) -> list[tuple[RepoFileSnapshotRecord, RepoSubjectRecord]]:
        stmt = (
            select(RepoFileSnapshotRecord, RepoSubjectRecord)
            .join(RepoSubjectRecord, RepoFileSnapshotRecord.subject_id == RepoSubjectRecord.id)
            .where(RepoFileSnapshotRecord.run_id == run_id)
            .order_by(RepoSubjectRecord.subject_path)
            .offset(offset)
            .limit(limit)
        )
        if ingest_status:
            stmt = stmt.where(RepoFileSnapshotRecord.ingest_status == ingest_status)

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_ingested_for_run(
        self,
        *,
        run_id: str,
    ) -> list[tuple[RepoFileSnapshotRecord, RepoSubjectRecord]]:
        stmt = (
            select(RepoFileSnapshotRecord, RepoSubjectRecord)
            .join(RepoSubjectRecord, RepoFileSnapshotRecord.subject_id == RepoSubjectRecord.id)
            .where(
                RepoFileSnapshotRecord.run_id == run_id,
                RepoFileSnapshotRecord.ingest_status == "ingested",
                RepoSubjectRecord.subject_type == "file",
            )
            .order_by(RepoSubjectRecord.subject_path)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_for_run_all(self, *, run_id: str) -> list[tuple[RepoFileSnapshotRecord, RepoSubjectRecord]]:
        """Return all file snapshots for a run without pagination limits."""
        stmt = (
            select(RepoFileSnapshotRecord, RepoSubjectRecord)
            .join(RepoSubjectRecord, RepoFileSnapshotRecord.subject_id == RepoSubjectRecord.id)
            .where(RepoFileSnapshotRecord.run_id == run_id)
            .order_by(RepoSubjectRecord.subject_path)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
