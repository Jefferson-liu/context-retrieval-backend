from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFullSummaryDiagnosticRecord


class RepoFullSummaryDiagnosticRepository:
    """Persistence for repo-full-summary diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        repo_full_summary_run_id: str,
        severity: str,
        message: str,
        details: dict | None = None,
    ) -> RepoFullSummaryDiagnosticRecord:
        record = RepoFullSummaryDiagnosticRecord(
            id=str(uuid4()),
            repo_full_summary_run_id=repo_full_summary_run_id,
            severity=severity,
            message=message,
            details=details,
        )
        self.session.add(record)
        await self.session.flush()
        return record
