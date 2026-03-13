from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoManagerSegmentSummaryRecord


class RepoManagerSegmentSummaryRepository:
    """Persistence operations for LLM-generated segment architecture summaries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        repo_manager_run_id: str,
        group_id: str,
        source_run_id: str,
        source_file_summary_run_id: str,
        name: str,
        overall_summary: str,
        business_purpose: str,
        responsibilities: list[str],
        tags: list[str],
        representative_subject_ids: list[str],
        mermaid_diagram: str | None,
        is_infrastructure: bool,
        confidence: float,
        raw_output: dict,
        input_hash: str,
    ) -> RepoManagerSegmentSummaryRecord:
        stmt = select(RepoManagerSegmentSummaryRecord).where(
            RepoManagerSegmentSummaryRecord.repo_manager_run_id == repo_manager_run_id,
            RepoManagerSegmentSummaryRecord.group_id == group_id,
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            record = RepoManagerSegmentSummaryRecord(
                repo_manager_run_id=repo_manager_run_id,
                group_id=group_id,
                source_run_id=source_run_id,
                source_file_summary_run_id=source_file_summary_run_id,
                name=name,
                overall_summary=overall_summary,
                business_purpose=business_purpose,
                responsibilities=responsibilities,
                tags=tags,
                representative_subject_ids=representative_subject_ids,
                mermaid_diagram=mermaid_diagram,
                is_infrastructure=is_infrastructure,
                confidence=confidence,
                raw_output=raw_output,
                input_hash=input_hash,
            )
            self.session.add(record)
        else:
            record.source_run_id = source_run_id
            record.source_file_summary_run_id = source_file_summary_run_id
            record.name = name
            record.overall_summary = overall_summary
            record.business_purpose = business_purpose
            record.responsibilities = responsibilities
            record.tags = tags
            record.representative_subject_ids = representative_subject_ids
            record.mermaid_diagram = mermaid_diagram
            record.is_infrastructure = is_infrastructure
            record.confidence = confidence
            record.raw_output = raw_output
            record.input_hash = input_hash
        await self.session.flush()
        return record
