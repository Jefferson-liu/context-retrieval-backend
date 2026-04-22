from __future__ import annotations

from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFileSummaryUsageRecord, RepoSubjectRecord


class RepoFileSummaryUsageRepository:
    """Persistence for per-file token usage and agent trace records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        file_summary_run_id: str,
        subject_id: str,
        model_provider: str,
        model_name: str,
        status: str,
        error_message: str | None = None,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        total_tokens: int = 0,
        cached_input_tokens: int = 0,
        reasoning_tokens: int = 0,
        llm_step_count: int = 0,
        tool_call_count: int = 0,
        duration_ms: int | None = None,
        steps: list | None = None,
    ) -> RepoFileSummaryUsageRecord:
        """Insert one usage record for a single file summarization attempt."""

        record = RepoFileSummaryUsageRecord(
            id=str(uuid4()),
            file_summary_run_id=file_summary_run_id,
            subject_id=subject_id,
            model_provider=model_provider,
            model_name=model_name,
            status=status,
            error_message=error_message,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=cached_input_tokens,
            reasoning_tokens=reasoning_tokens,
            llm_step_count=llm_step_count,
            tool_call_count=tool_call_count,
            duration_ms=duration_ms,
            steps=steps or [],
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_for_run(
        self,
        *,
        file_summary_run_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        subject_path_prefix: str | None = None,
    ) -> list[tuple[RepoFileSummaryUsageRecord, RepoSubjectRecord]]:
        """Return usage records for one file-summary run with subject metadata."""

        stmt = (
            select(RepoFileSummaryUsageRecord, RepoSubjectRecord)
            .join(RepoSubjectRecord, RepoFileSummaryUsageRecord.subject_id == RepoSubjectRecord.id)
            .where(RepoFileSummaryUsageRecord.file_summary_run_id == file_summary_run_id)
            .order_by(desc(RepoFileSummaryUsageRecord.total_tokens))
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(RepoFileSummaryUsageRecord.status == status)
        if subject_path_prefix:
            stmt = stmt.where(RepoSubjectRecord.subject_path.like(f"{subject_path_prefix}%"))

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def aggregate_for_run(
        self,
        *,
        file_summary_run_id: str,
    ) -> dict:
        """Return aggregated token totals and counts for a file-summary run."""

        stmt = (
            select(
                func.count().label("file_count"),
                func.count().filter(RepoFileSummaryUsageRecord.status == "completed").label("completed_count"),
                func.count().filter(RepoFileSummaryUsageRecord.status == "failed").label("failed_count"),
                func.count().filter(RepoFileSummaryUsageRecord.status == "skipped").label("skipped_count"),
                func.coalesce(func.sum(RepoFileSummaryUsageRecord.total_input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(RepoFileSummaryUsageRecord.total_output_tokens), 0).label("total_output_tokens"),
                func.coalesce(func.sum(RepoFileSummaryUsageRecord.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(RepoFileSummaryUsageRecord.cached_input_tokens), 0).label("cached_input_tokens"),
                func.coalesce(func.sum(RepoFileSummaryUsageRecord.reasoning_tokens), 0).label("reasoning_tokens"),
                func.avg(RepoFileSummaryUsageRecord.duration_ms).label("avg_duration_ms"),
            )
            .where(RepoFileSummaryUsageRecord.file_summary_run_id == file_summary_run_id)
        )
        row = (await self.session.execute(stmt)).one()
        file_count = row.file_count or 0
        total_tokens = row.total_tokens or 0
        return {
            "file_count": file_count,
            "completed_count": row.completed_count or 0,
            "failed_count": row.failed_count or 0,
            "skipped_count": row.skipped_count or 0,
            "total_input_tokens": row.total_input_tokens or 0,
            "total_output_tokens": row.total_output_tokens or 0,
            "total_tokens": total_tokens,
            "cached_input_tokens": row.cached_input_tokens or 0,
            "reasoning_tokens": row.reasoning_tokens or 0,
            "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms is not None else None,
            "avg_tokens_per_file": round(total_tokens / file_count, 1) if file_count else None,
        }
