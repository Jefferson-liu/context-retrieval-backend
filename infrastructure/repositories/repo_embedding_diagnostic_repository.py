from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoEmbeddingDiagnosticRecord


class RepoEmbeddingDiagnosticRepository:
    """Persistence for non-fatal diagnostics raised during repo embedding generation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        embedding_run_id: str,
        subject_id: str,
        severity: str,
        message: str,
        details: dict | None,
    ) -> RepoEmbeddingDiagnosticRecord:
        record = RepoEmbeddingDiagnosticRecord(
            id=str(uuid4()),
            embedding_run_id=embedding_run_id,
            subject_id=subject_id,
            severity=severity,
            message=message,
            details=details,
        )
        self.session.add(record)
        await self.session.flush()
        return record
