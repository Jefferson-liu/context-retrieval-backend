from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoGroupSummaryDiagnosticRecord


class RepoGroupSummaryDiagnosticRepository:
    """Persistence for group-summary diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        group_summary_run_id: str,
        group_id: str,
        severity: str,
        message: str,
        details: dict | None = None,
    ) -> RepoGroupSummaryDiagnosticRecord:
        record = RepoGroupSummaryDiagnosticRecord(
            id=str(uuid4()),
            repo_manager_run_id=group_summary_run_id,
            group_id=group_id,
            severity=severity,
            message=message,
            details=details,
        )
        self.session.add(record)
        await self.session.flush()
        return record
