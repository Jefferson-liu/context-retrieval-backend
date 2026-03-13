from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import (
    RepoGroupSummaryRecord,
    RepoSummaryGroupMemberRecord,
    RepoSummaryGroupRecord,
    RepoSubjectRecord,
)


class RepoSummaryGroupRepository:
    """Persistence and read operations for deterministic summary groups and members."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def clear_for_run(self, *, group_summary_run_id: str) -> None:
        """Remove existing groups/members/summaries for a run before rebuilding."""
        await self.session.execute(
            delete(RepoGroupSummaryRecord).where(RepoGroupSummaryRecord.group_summary_run_id == group_summary_run_id)
        )
        await self.session.execute(
            delete(RepoSummaryGroupMemberRecord).where(
                RepoSummaryGroupMemberRecord.group_summary_run_id == group_summary_run_id
            )
        )
        await self.session.execute(
            delete(RepoSummaryGroupRecord).where(RepoSummaryGroupRecord.group_summary_run_id == group_summary_run_id)
        )
        await self.session.flush()

    async def create_groups(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        records = [
            RepoSummaryGroupRecord(
                group_summary_run_id=row["group_summary_run_id"],
                group_id=row["group_id"],
                source_run_id=row["source_run_id"],
                source_file_summary_run_id=row["source_file_summary_run_id"],
                group_key=row["group_key"],
                group_label=row["group_label"],
                layer_hint=row["layer_hint"],
                member_count=row["member_count"],
                dependency_neighbor_count=row["dependency_neighbor_count"],
                is_infrastructure_seed=row["is_infrastructure_seed"],
                heuristics=row.get("heuristics") or {},
            )
            for row in rows
        ]
        self.session.add_all(records)
        await self.session.flush()
        return len(records)

    async def create_group_members(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        records = [
            RepoSummaryGroupMemberRecord(
                group_summary_run_id=row["group_summary_run_id"],
                group_id=row["group_id"],
                subject_id=row["subject_id"],
                rank=row["rank"],
                is_representative=row.get("is_representative", False),
                membership_reason=row.get("membership_reason", "group_assignment"),
            )
            for row in rows
        ]
        self.session.add_all(records)
        await self.session.flush()
        return len(records)

    async def list_groups_for_run(
        self,
        *,
        group_summary_run_id: str,
        limit: int,
        offset: int,
        layer_hint: str | None,
        is_infrastructure: bool | None,
        group_key_prefix: str | None,
    ) -> list[tuple[RepoSummaryGroupRecord, RepoGroupSummaryRecord | None]]:
        stmt = (
            select(RepoSummaryGroupRecord, RepoGroupSummaryRecord)
            .outerjoin(
                RepoGroupSummaryRecord,
                (RepoGroupSummaryRecord.group_summary_run_id == RepoSummaryGroupRecord.group_summary_run_id)
                & (RepoGroupSummaryRecord.group_id == RepoSummaryGroupRecord.group_id),
            )
            .where(RepoSummaryGroupRecord.group_summary_run_id == group_summary_run_id)
            .order_by(RepoSummaryGroupRecord.group_key)
            .offset(offset)
            .limit(limit)
        )
        if layer_hint:
            stmt = stmt.where(RepoSummaryGroupRecord.layer_hint == layer_hint)
        if is_infrastructure is not None:
            stmt = stmt.where(RepoGroupSummaryRecord.is_infrastructure == is_infrastructure)
        if group_key_prefix:
            stmt = stmt.where(RepoSummaryGroupRecord.group_key.like(f"{group_key_prefix}%"))

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_members_for_groups(
        self,
        *,
        group_summary_run_id: str,
        group_ids: list[str],
    ) -> dict[str, list[tuple[RepoSummaryGroupMemberRecord, RepoSubjectRecord]]]:
        if not group_ids:
            return {}

        stmt = (
            select(RepoSummaryGroupMemberRecord, RepoSubjectRecord)
            .join(RepoSubjectRecord, RepoSubjectRecord.id == RepoSummaryGroupMemberRecord.subject_id)
            .where(
                RepoSummaryGroupMemberRecord.group_summary_run_id == group_summary_run_id,
                RepoSummaryGroupMemberRecord.group_id.in_(group_ids),
            )
            .order_by(RepoSummaryGroupMemberRecord.group_id, RepoSummaryGroupMemberRecord.rank, RepoSubjectRecord.subject_path)
        )
        result = await self.session.execute(stmt)

        payload: dict[str, list[tuple[RepoSummaryGroupMemberRecord, RepoSubjectRecord]]] = {}
        for member, subject in result.all():
            payload.setdefault(member.group_id, []).append((member, subject))
        return payload

    async def get_group_with_summary(
        self,
        *,
        group_summary_run_id: str,
        group_id: str | None,
        group_key: str | None,
    ) -> tuple[RepoSummaryGroupRecord, RepoGroupSummaryRecord | None] | None:
        stmt = (
            select(RepoSummaryGroupRecord, RepoGroupSummaryRecord)
            .outerjoin(
                RepoGroupSummaryRecord,
                (RepoGroupSummaryRecord.group_summary_run_id == RepoSummaryGroupRecord.group_summary_run_id)
                & (RepoGroupSummaryRecord.group_id == RepoSummaryGroupRecord.group_id),
            )
            .where(RepoSummaryGroupRecord.group_summary_run_id == group_summary_run_id)
            .limit(1)
        )
        if group_id:
            stmt = stmt.where(RepoSummaryGroupRecord.group_id == group_id)
        elif group_key:
            stmt = stmt.where(RepoSummaryGroupRecord.group_key == group_key)
        else:
            return None

        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]
