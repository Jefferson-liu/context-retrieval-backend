from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoParseDiagnosticRecord


class RepoDiagnosticRepository:
    """Persistence for parser diagnostics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_many(self, diagnostics: list[dict]) -> int:
        for item in diagnostics:
            self.session.add(
                RepoParseDiagnosticRecord(
                    id=str(uuid4()),
                    run_id=item["run_id"],
                    subject_id=item["subject_id"],
                    language=item.get("language"),
                    severity=item.get("severity", "warning"),
                    message=item["message"],
                    line=item.get("line"),
                    column=item.get("column"),
                )
            )
        await self.session.flush()
        return len(diagnostics)
