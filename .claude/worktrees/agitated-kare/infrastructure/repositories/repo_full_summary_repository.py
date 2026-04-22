from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFullSummaryRecord


class RepoFullSummaryRepository:
    """Persistence operations for repo-level README summary artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        repo_full_summary_run_id: str,
        source_run_id: str,
        source_file_summary_run_id: str,
        readme_markdown: str,
        raw_output: dict,
        input_hash: str,
    ) -> RepoFullSummaryRecord:
        stmt = select(RepoFullSummaryRecord).where(
            RepoFullSummaryRecord.repo_full_summary_run_id == repo_full_summary_run_id,
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            record = RepoFullSummaryRecord(
                repo_full_summary_run_id=repo_full_summary_run_id,
                source_run_id=source_run_id,
                source_file_summary_run_id=source_file_summary_run_id,
                readme_markdown=readme_markdown,
                raw_output=raw_output,
                input_hash=input_hash,
            )
            self.session.add(record)
        else:
            record.source_run_id = source_run_id
            record.source_file_summary_run_id = source_file_summary_run_id
            record.readme_markdown = readme_markdown
            record.raw_output = raw_output
            record.input_hash = input_hash
        await self.session.flush()
        return record

    async def get_for_run(self, *, repo_full_summary_run_id: str) -> RepoFullSummaryRecord | None:
        stmt = select(RepoFullSummaryRecord).where(
            RepoFullSummaryRecord.repo_full_summary_run_id == repo_full_summary_run_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
