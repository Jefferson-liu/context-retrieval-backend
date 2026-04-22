from __future__ import annotations

from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFileSummaryDiagnosticRecord, RepoSubjectRecord


class RepoFileSummaryDiagnosticRepository:
    """Persistence for repository summary file_summary diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        file_summary_run_id: str,
        subject_id: str,
        severity: str,
        message: str,
        details: dict | None = None,
    ) -> RepoFileSummaryDiagnosticRecord:
        record = RepoFileSummaryDiagnosticRecord(
            id=str(uuid4()),
            file_summary_run_id=file_summary_run_id,
            subject_id=subject_id,
            severity=severity,
            message=message,
            details=details,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_for_file_summary(
        self,
        *,
        file_summary_run_id: str,
        limit: int,
        offset: int,
        severity: str | None = None,
        subject_path_prefix: str | None = None,
    ) -> list[tuple[RepoFileSummaryDiagnosticRecord, RepoSubjectRecord]]:
        """Return diagnostics for one file-summary run with subject metadata."""

        stmt = (
            select(RepoFileSummaryDiagnosticRecord, RepoSubjectRecord)
            .join(RepoSubjectRecord, RepoFileSummaryDiagnosticRecord.subject_id == RepoSubjectRecord.id)
            .where(RepoFileSummaryDiagnosticRecord.file_summary_run_id == file_summary_run_id)
            .order_by(desc(RepoFileSummaryDiagnosticRecord.created_at))
            .offset(offset)
            .limit(limit)
        )
        if severity:
            stmt = stmt.where(RepoFileSummaryDiagnosticRecord.severity == severity)
        if subject_path_prefix:
            stmt = stmt.where(RepoSubjectRecord.subject_path.like(f"{subject_path_prefix}%"))

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
