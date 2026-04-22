from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoFileSnapshotRecord, RepoSubjectRecord, RepoFileSummaryRecord


class RepoFileSummaryRepository:
    """Persistence and query operations for repository summary artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        file_summary_run_id: str,
        source_run_id: str,
        subject_id: str,
        overall_summary: str,
        file_cluster: list[str],
        important_relationships: list[str],
        group_function: str | None,
        raw_output: dict,
        input_hash: str,
    ) -> RepoFileSummaryRecord:
        stmt = select(RepoFileSummaryRecord).where(
            RepoFileSummaryRecord.file_summary_run_id == file_summary_run_id,
            RepoFileSummaryRecord.subject_id == subject_id,
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            record = RepoFileSummaryRecord(
                file_summary_run_id=file_summary_run_id,
                source_run_id=source_run_id,
                subject_id=subject_id,
                overall_summary=overall_summary,
                file_cluster=file_cluster,
                important_relationships=important_relationships,
                group_function=group_function,
                raw_output=raw_output,
                input_hash=input_hash,
            )
            self.session.add(record)
        else:
            record.source_run_id = source_run_id
            record.overall_summary = overall_summary
            record.file_cluster = file_cluster
            record.important_relationships = important_relationships
            record.group_function = group_function
            record.raw_output = raw_output
            record.input_hash = input_hash
        await self.session.flush()
        return record

    async def find_by_subject_and_hash(
        self,
        *,
        subject_id: str,
        input_hash: str,
    ) -> RepoFileSummaryRecord | None:
        """Return any existing summary with the same content hash, or None."""
        stmt = (
            select(RepoFileSummaryRecord)
            .where(
                RepoFileSummaryRecord.subject_id == subject_id,
                RepoFileSummaryRecord.input_hash == input_hash,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_file_summary(
        self,
        *,
        file_summary_run_id: str,
        source_run_id: str,
        limit: int,
        offset: int,
        language: str | None = None,
        parse_status: str | None = None,
        subject_path_prefix: str | None = None,
    ) -> list[tuple[RepoFileSummaryRecord, RepoSubjectRecord, RepoFileSnapshotRecord | None]]:
        stmt = (
            select(RepoFileSummaryRecord, RepoSubjectRecord, RepoFileSnapshotRecord)
            .join(RepoSubjectRecord, RepoFileSummaryRecord.subject_id == RepoSubjectRecord.id)
            .outerjoin(
                RepoFileSnapshotRecord,
                (RepoFileSnapshotRecord.run_id == source_run_id)
                & (RepoFileSnapshotRecord.subject_id == RepoFileSummaryRecord.subject_id),
            )
            .where(RepoFileSummaryRecord.file_summary_run_id == file_summary_run_id)
            .order_by(RepoSubjectRecord.subject_path)
            .offset(offset)
            .limit(limit)
        )

        if language:
            stmt = stmt.where(RepoSubjectRecord.language == language)
        if parse_status:
            stmt = stmt.where(RepoFileSnapshotRecord.parse_status == parse_status)
        if subject_path_prefix:
            stmt = stmt.where(RepoSubjectRecord.subject_path.like(f"{subject_path_prefix}%"))

        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def list_for_file_summary_all(
        self,
        *,
        file_summary_run_id: str,
    ) -> list[tuple[RepoFileSummaryRecord, RepoSubjectRecord, RepoFileSnapshotRecord | None]]:
        """Return all summary rows for one file_summary run with subject/snapshot metadata."""
        stmt = (
            select(RepoFileSummaryRecord, RepoSubjectRecord, RepoFileSnapshotRecord)
            .join(RepoSubjectRecord, RepoFileSummaryRecord.subject_id == RepoSubjectRecord.id)
            .outerjoin(
                RepoFileSnapshotRecord,
                (RepoFileSnapshotRecord.run_id == RepoFileSummaryRecord.source_run_id)
                & (RepoFileSnapshotRecord.subject_id == RepoFileSummaryRecord.subject_id),
            )
            .where(
                RepoFileSummaryRecord.file_summary_run_id == file_summary_run_id,
                RepoSubjectRecord.subject_type == "file",
            )
            .order_by(RepoSubjectRecord.subject_path)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def list_for_subject_ids(
        self,
        *,
        file_summary_run_id: str,
        source_run_id: str,
        subject_ids: list[str],
    ) -> list[tuple[RepoFileSummaryRecord, RepoSubjectRecord, RepoFileSnapshotRecord | None]]:
        """Return summaries for an explicit subject id set."""
        if not subject_ids:
            return []
        stmt = (
            select(RepoFileSummaryRecord, RepoSubjectRecord, RepoFileSnapshotRecord)
            .join(RepoSubjectRecord, RepoFileSummaryRecord.subject_id == RepoSubjectRecord.id)
            .outerjoin(
                RepoFileSnapshotRecord,
                (RepoFileSnapshotRecord.run_id == source_run_id)
                & (RepoFileSnapshotRecord.subject_id == RepoFileSummaryRecord.subject_id),
            )
            .where(
                RepoFileSummaryRecord.file_summary_run_id == file_summary_run_id,
                RepoFileSummaryRecord.subject_id.in_(subject_ids),
            )
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]
