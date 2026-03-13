from __future__ import annotations

from dataclasses import dataclass

from infrastructure.models import RepoGroupSummaryRunRecord
from schemas.repo_knowledge_repo_manager import RepoManagerRunCreateRequest
from services.repo_knowledge.group_summary_service import (
    RepoGroupSummaryError,
    RepoGroupSummaryWorker,
    RepoKnowledgeGroupSummaryService,
)


@dataclass(slots=True)
class _LegacyGroupSummaryCreateRequest:
    source_file_summary_run_id: str
    force_resummarize: bool


class RepoManagerError(RepoGroupSummaryError):
    """Raised when a repo-manager run request cannot be accepted."""


class RepoKnowledgeRepoManagerService(RepoKnowledgeGroupSummaryService):
    """Canonical repo-manager service built on the existing persistence layer."""

    async def create_repo_manager_run(
        self,
        payload: RepoManagerRunCreateRequest,
    ) -> RepoGroupSummaryRunRecord:
        return await super().create_group_summary_run(
            payload=_LegacyGroupSummaryCreateRequest(
                source_file_summary_run_id=payload.source_file_summary_run_id,
                force_resummarize=payload.force_rerepo_manager,
            )
        )

    async def get_repo_manager_run_status(self, *, repo_manager_run_id: str):
        return await super().get_group_summary_run_status(group_summary_run_id=repo_manager_run_id)

    async def get_architecture_artifact(self, *, repo_manager_run_id: str):
        return await super().get_architecture_artifact(group_summary_run_id=repo_manager_run_id)

    async def list_repo_manager_segments(
        self,
        *,
        repo_manager_run_id: str,
        limit: int,
        offset: int,
        layer_hint: str | None,
        is_infrastructure: bool | None,
        group_key_prefix: str | None,
        include_members: bool,
    ):
        return await super().list_group_summaries(
            group_summary_run_id=repo_manager_run_id,
            limit=limit,
            offset=offset,
            layer_hint=layer_hint,
            is_infrastructure=is_infrastructure,
            group_key_prefix=group_key_prefix,
            include_members=include_members,
        )

    async def latest_repo_manager_segments_for_source_run(
        self,
        *,
        source_run_id: str,
        limit: int,
        offset: int,
        include_members: bool,
    ):
        return await super().latest_group_summaries_for_source_run(
            source_run_id=source_run_id,
            limit=limit,
            offset=offset,
            include_members=include_members,
        )


class RepoManagerWorker(RepoGroupSummaryWorker):
    """Canonical repo-manager background worker."""

    async def execute(self, *, repo_manager_run_id: str) -> None:
        await super().execute(group_summary_run_id=repo_manager_run_id)