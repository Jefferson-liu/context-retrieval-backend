from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import (
    RepoEmbeddingRunRecord,
    RepoFullSummaryRunRecord,
    RepoFileSummaryRunRecord,
    RepoGroupSummaryRunRecord,
    RepoRunRecord,
)
from infrastructure.repositories import (
    RepoEmbeddingRunRepository,
    RepoFullSummaryRunRepository,
    RepoFileSummaryRunRepository,
    RepoGroupSummaryRunRepository,
    RepoRunRepository,
)
from schemas.repo_knowledge import RepoRunCreateRequest
from schemas.repo_knowledge_embedding import RepoEmbeddingRunCreateRequest
from schemas.repo_knowledge_file_summary import RepoFileSummaryRunCreateRequest
from schemas.repo_knowledge_repo_full_summary import RepoFullSummaryRunCreateRequest
from schemas.repo_knowledge_pipeline import RepoPipelineRunCreateRequest
from services.repo_knowledge.background_runner import get_repo_ingestion_runner
from services.repo_knowledge.embedding_background_runner import get_repo_embedding_runner
from services.repo_knowledge.embedding_service import RepoEmbeddingError, RepoKnowledgeEmbeddingService
from services.repo_knowledge.file_summary_background_runner import get_repo_file_summary_runner
from services.repo_knowledge.file_summary_service import (
    RepoKnowledgeFileSummaryService,
    RepoFileSummaryError,
)
from services.repo_knowledge.repo_manager_background_runner import get_repo_manager_runner
from services.repo_knowledge.repo_manager_service import RepoKnowledgeRepoManagerService, RepoManagerError
from schemas.repo_knowledge_repo_manager import RepoManagerRunCreateRequest
from services.repo_knowledge.repo_full_summary_background_runner import get_repo_full_summary_runner
from services.repo_knowledge.repo_full_summary_service import RepoFullSummaryError, RepoKnowledgeRepoFullSummaryService
from services.repo_knowledge.ingestion_service import RepoIngestionError, RepoKnowledgeService

logger = logging.getLogger(__name__)

PipelineStatus = Literal["queued", "in_progress", "completed", "failed"]
PipelineStage = Literal[
    "queued",
    "ingestion",
    "file_summary",
    "repo_full_summary",
    "embedding",
    "repo_manager",
    "architecture",
    "completed",
    "failed",
]


class RepoPipelineError(Exception):
    """Raised when a pipeline run request cannot be accepted."""


@dataclass(slots=True)
class RepoPipelineQueueItem:
    """One queued pipeline orchestration task keyed by source run id."""

    source_run_id: str
    tenant_id: str
    user_id: str
    force_reingest: bool = False
    force_refile_summary: bool = False
    force_rerepo_summary: bool = False
    force_reembed: bool = False
    force_rerepo_manager: bool = False
    file_summary_run_id: str | None = None
    repo_full_summary_run_id: str | None = None
    embedding_run_id: str | None = None
    repo_manager_run_id: str | None = None
    ingestion_enqueued: bool = False
    file_summary_enqueued: bool = False
    repo_full_summary_enqueued: bool = False
    embedding_enqueued: bool = False
    repo_manager_enqueued: bool = False


@dataclass(slots=True)
class RepoPipelineStatusSnapshot:
    """Resolved pipeline status and linked stage runs for one source run."""

    source_run: RepoRunRecord
    status: PipelineStatus
    stage: PipelineStage
    file_summary_run: RepoFileSummaryRunRecord | None
    repo_full_summary_run: RepoFullSummaryRunRecord | None
    embedding_run: RepoEmbeddingRunRecord | None
    repo_manager_run: RepoGroupSummaryRunRecord | None
    error_message: str | None
    stage_error_message: str | None


class RepoKnowledgePipelineService:
    """Application service for repo-knowledge pipeline APIs."""

    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.repo_full_summary_run_repo = RepoFullSummaryRunRepository(session)
        self.embedding_run_repo = RepoEmbeddingRunRepository(session)
        self.group_summary_run_repo = RepoGroupSummaryRunRepository(session)

    async def create_pipeline_run(
        self,
        payload: RepoPipelineRunCreateRequest,
    ) -> tuple[RepoRunRecord, RepoPipelineQueueItem]:
        """Create the source ingestion run and return queued orchestration metadata."""

        run_payload = RepoRunCreateRequest(
            source_type=payload.source_type,
            source_path=payload.source_path,
            repo_address=payload.repo_address,
            include_extensions=payload.include_extensions,
            exclude_globs=payload.exclude_globs,
            force_reingest=payload.force_reingest,
        )
        ingestion_service = RepoKnowledgeService(
            self.session,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        try:
            source_run = await ingestion_service.create_run(run_payload)
        except RepoIngestionError as exc:
            raise RepoPipelineError(str(exc)) from exc

        queue_item = RepoPipelineQueueItem(
            source_run_id=source_run.id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            force_reingest=payload.force_reingest,
            force_refile_summary=payload.force_refile_summary,
            force_rerepo_summary=payload.force_rerepo_summary,
            force_reembed=payload.force_reembed,
            force_rerepo_manager=payload.force_rerepo_manager,
        )
        return source_run, queue_item

    async def get_pipeline_status(self, *, source_run_id: str) -> RepoPipelineStatusSnapshot | None:
        """Resolve end-to-end stage status for one source run id."""

        source_run = await self.run_repo.get_scoped(
            source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
        )
        if source_run is None:
            return None

        file_summary_run = await self._pick_file_summary_run(source_run_id=source_run.id)
        repo_full_summary_run = await self._pick_repo_full_summary_run(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id if file_summary_run else None,
        )
        embedding_run = await self._pick_embedding_run(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id if file_summary_run else None,
        )
        repo_manager_run = await self._pick_repo_manager_run(
            source_run_id=source_run.id,
            source_file_summary_run_id=file_summary_run.id if file_summary_run else None,
        )
        status, stage, error_message, stage_error_message = _resolve_pipeline_status(
            source_run=source_run,
            file_summary_run=file_summary_run,
            repo_full_summary_run=repo_full_summary_run,
            embedding_run=embedding_run,
            repo_manager_run=repo_manager_run,
        )
        return RepoPipelineStatusSnapshot(
            source_run=source_run,
            status=status,
            stage=stage,
            file_summary_run=file_summary_run,
            repo_full_summary_run=repo_full_summary_run,
            embedding_run=embedding_run,
            repo_manager_run=repo_manager_run,
            error_message=error_message,
            stage_error_message=stage_error_message,
        )

    async def _pick_file_summary_run(self, *, source_run_id: str) -> RepoFileSummaryRunRecord | None:
        active = await self.file_summary_run_repo.latest_for_source(
            source_run_id=source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            statuses=["queued", "in_progress"],
        )
        if active is not None:
            return active

        completed = await self.file_summary_run_repo.latest_for_source(
            source_run_id=source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            statuses=["completed"],
        )
        if completed is not None:
            return completed

        return await self.file_summary_run_repo.latest_for_source(
            source_run_id=source_run_id,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            statuses=["failed"],
        )

    async def _pick_repo_full_summary_run(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str | None,
    ) -> RepoFullSummaryRunRecord | None:
        if source_file_summary_run_id is None:
            return await self.repo_full_summary_run_repo.latest_for_source(
                source_run_id=source_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        for statuses in (["queued", "in_progress"], ["completed"], ["failed"]):
            run = await self.repo_full_summary_run_repo.latest_for_source_file_summary(
                source_run_id=source_run_id,
                source_file_summary_run_id=source_file_summary_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                statuses=statuses,
            )
            if run is not None:
                return run
        return None

    async def _pick_embedding_run(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str | None,
    ) -> RepoEmbeddingRunRecord | None:
        if source_file_summary_run_id is None:
            return await self.embedding_run_repo.latest_for_source(
                source_run_id=source_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        for statuses in (["queued", "in_progress"], ["completed"], ["failed"]):
            run = await self.embedding_run_repo.latest_for_source_file_summary(
                source_run_id=source_run_id,
                source_file_summary_run_id=source_file_summary_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                statuses=statuses,
            )
            if run is not None:
                return run
        return None

    async def _pick_repo_manager_run(
        self,
        *,
        source_run_id: str,
        source_file_summary_run_id: str | None,
    ) -> RepoGroupSummaryRunRecord | None:
        if source_file_summary_run_id is None:
            return await self.group_summary_run_repo.latest_for_source(
                source_run_id=source_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
            )

        for statuses in (["queued", "in_progress"], ["completed"], ["failed"]):
            run = await self.group_summary_run_repo.latest_for_source_file_summary(
                source_run_id=source_run_id,
                source_file_summary_run_id=source_file_summary_run_id,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                statuses=statuses,
            )
            if run is not None:
                return run
        return None


class RepoKnowledgePipelineCoordinator:
    """Coordinates stage transitions for one queued pipeline task."""

    def __init__(self, session: AsyncSession, *, task: RepoPipelineQueueItem) -> None:
        self.session = session
        self.task = task
        self.run_repo = RepoRunRepository(session)
        self.file_summary_run_repo = RepoFileSummaryRunRepository(session)
        self.repo_full_summary_run_repo = RepoFullSummaryRunRepository(session)
        self.embedding_run_repo = RepoEmbeddingRunRepository(session)
        self.group_summary_run_repo = RepoGroupSummaryRunRepository(session)

    async def advance_once(self) -> bool:
        """Advance one step; return True when pipeline is terminal."""

        source_run = await self.run_repo.get_scoped(
            self.task.source_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if source_run is None:
            logger.warning(
                "Pipeline source run not found; stopping orchestration source_run_id=%s tenant=%s user=%s",
                self.task.source_run_id,
                self.task.tenant_id,
                self.task.user_id,
            )
            return True

        if source_run.status == "queued":
            if not self.task.ingestion_enqueued:
                ingestion_runner = get_repo_ingestion_runner()
                await ingestion_runner.enqueue(
                    source_run.id,
                    force_reingest=self.task.force_reingest,
                )
                self.task.ingestion_enqueued = True
            return False
        if source_run.status == "in_progress":
            return False
        if source_run.status == "failed":
            return True
        self.task.ingestion_enqueued = False

        file_summary_terminal = await self._advance_file_summary_stage(source_run=source_run)
        if file_summary_terminal:
            return True
        if self.task.file_summary_run_id is None:
            return False
        file_summary_run = await self.file_summary_run_repo.get_scoped(
            self.task.file_summary_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if file_summary_run is None:
            return True
        if file_summary_run.status != "completed":
            return file_summary_run.status == "failed"

        repo_full_terminal = await self._advance_repo_full_summary_stage(
            source_run=source_run,
            file_summary_run=file_summary_run,
        )
        if repo_full_terminal:
            return True
        if self.task.repo_full_summary_run_id is None:
            return False
        repo_full_summary_run = await self.repo_full_summary_run_repo.get_scoped(
            self.task.repo_full_summary_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if repo_full_summary_run is None:
            return True
        if repo_full_summary_run.status != "completed":
            return repo_full_summary_run.status == "failed"

        embedding_terminal = await self._advance_embedding_stage(source_run=source_run, file_summary_run=file_summary_run)
        if embedding_terminal:
            return True
        if self.task.embedding_run_id is None:
            return False
        embedding_run = await self.embedding_run_repo.get_scoped(
            self.task.embedding_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if embedding_run is None:
            return True
        if embedding_run.status != "completed":
            return embedding_run.status == "failed"

        repo_manager_terminal = await self._advance_repo_manager_stage(
            source_run=source_run,
            file_summary_run=file_summary_run,
        )
        if repo_manager_terminal:
            return True
        if self.task.repo_manager_run_id is None:
            return False
        repo_manager_run = await self.group_summary_run_repo.get_scoped(
            self.task.repo_manager_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if repo_manager_run is None:
            return True
        return repo_manager_run.status in {"completed", "failed"}

    async def _advance_file_summary_stage(self, *, source_run: RepoRunRecord) -> bool:
        if self.task.file_summary_run_id is None:
            if not self.task.force_refile_summary:
                completed = await self.file_summary_run_repo.latest_for_source(
                    source_run_id=source_run.id,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                    statuses=["completed"],
                )
                if completed is not None:
                    self.task.file_summary_run_id = completed.id
                    self.task.file_summary_enqueued = False
                    return False

            active = await self.file_summary_run_repo.latest_for_source(
                source_run_id=source_run.id,
                tenant_id=self.task.tenant_id,
                user_id=self.task.user_id,
                statuses=["queued", "in_progress"],
            )
            if active is not None:
                self.task.file_summary_run_id = active.id
                self.task.file_summary_enqueued = False
            else:
                service = RepoKnowledgeFileSummaryService(
                    self.session,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                )
                try:
                    created = await service.create_file_summary_run(
                        RepoFileSummaryRunCreateRequest(
                            source_run_id=source_run.id,
                            force_refile_summary=self.task.force_refile_summary,
                        )
                    )
                except RepoFileSummaryError:
                    logger.exception("Pipeline file_summary stage failed to create run source_run_id=%s", source_run.id)
                    return True
                await self.session.commit()
                self.task.file_summary_run_id = created.id
                self.task.file_summary_enqueued = False

        file_summary_run = await self.file_summary_run_repo.get_scoped(
            self.task.file_summary_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if file_summary_run is None:
            return True
        if file_summary_run.status == "queued":
            if not self.task.file_summary_enqueued:
                runner = get_repo_file_summary_runner()
                await runner.enqueue(file_summary_run.id)
                self.task.file_summary_enqueued = True
            return False
        self.task.file_summary_enqueued = False
        return file_summary_run.status == "failed"

    async def _advance_repo_full_summary_stage(
        self,
        *,
        source_run: RepoRunRecord,
        file_summary_run: RepoFileSummaryRunRecord,
    ) -> bool:
        if self.task.repo_full_summary_run_id is None:
            if not self.task.force_rerepo_summary:
                completed = await self.repo_full_summary_run_repo.latest_for_source_file_summary(
                    source_run_id=source_run.id,
                    source_file_summary_run_id=file_summary_run.id,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                    statuses=["completed"],
                )
                if completed is not None:
                    self.task.repo_full_summary_run_id = completed.id
                    self.task.repo_full_summary_enqueued = False
                    return False

            active = await self.repo_full_summary_run_repo.latest_for_source_file_summary(
                source_run_id=source_run.id,
                source_file_summary_run_id=file_summary_run.id,
                tenant_id=self.task.tenant_id,
                user_id=self.task.user_id,
                statuses=["queued", "in_progress"],
            )
            if active is not None:
                self.task.repo_full_summary_run_id = active.id
                self.task.repo_full_summary_enqueued = False
            else:
                service = RepoKnowledgeRepoFullSummaryService(
                    self.session,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                )
                try:
                    created = await service.create_repo_full_summary_run(
                        RepoFullSummaryRunCreateRequest(
                            source_file_summary_run_id=file_summary_run.id,
                            force_rerepo_summary=self.task.force_rerepo_summary,
                        )
                    )
                except RepoFullSummaryError:
                    logger.exception(
                        "Pipeline repo-full-summary stage failed to create run source_run_id=%s file_summary_run_id=%s",
                        source_run.id,
                        file_summary_run.id,
                    )
                    return True
                await self.session.commit()
                self.task.repo_full_summary_run_id = created.id
                self.task.repo_full_summary_enqueued = False

        repo_full_summary_run = await self.repo_full_summary_run_repo.get_scoped(
            self.task.repo_full_summary_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if repo_full_summary_run is None:
            return True
        if repo_full_summary_run.status == "queued":
            if not self.task.repo_full_summary_enqueued:
                runner = get_repo_full_summary_runner()
                await runner.enqueue(repo_full_summary_run.id)
                self.task.repo_full_summary_enqueued = True
            return False
        self.task.repo_full_summary_enqueued = False
        return repo_full_summary_run.status == "failed"

    async def _advance_embedding_stage(
        self,
        *,
        source_run: RepoRunRecord,
        file_summary_run: RepoFileSummaryRunRecord,
    ) -> bool:
        if self.task.embedding_run_id is None:
            if not self.task.force_reembed:
                completed = await self.embedding_run_repo.latest_for_source_file_summary(
                    source_run_id=source_run.id,
                    source_file_summary_run_id=file_summary_run.id,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                    statuses=["completed"],
                )
                if completed is not None:
                    self.task.embedding_run_id = completed.id
                    self.task.embedding_enqueued = False
                    return False

            active = await self.embedding_run_repo.latest_for_source_file_summary(
                source_run_id=source_run.id,
                source_file_summary_run_id=file_summary_run.id,
                tenant_id=self.task.tenant_id,
                user_id=self.task.user_id,
                statuses=["queued", "in_progress"],
            )
            if active is not None:
                self.task.embedding_run_id = active.id
                self.task.embedding_enqueued = False
            else:
                service = RepoKnowledgeEmbeddingService(
                    self.session,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                )
                try:
                    created = await service.create_embedding_run(
                        RepoEmbeddingRunCreateRequest(
                            source_file_summary_run_id=file_summary_run.id,
                            source_run_id=source_run.id,
                            force_reembed=self.task.force_reembed,
                        )
                    )
                except RepoEmbeddingError:
                    logger.exception(
                        "Pipeline embedding stage failed to create run source_run_id=%s file_summary_run_id=%s",
                        source_run.id,
                        file_summary_run.id,
                    )
                    return True
                await self.session.commit()
                self.task.embedding_run_id = created.id
                self.task.embedding_enqueued = False

        embedding_run = await self.embedding_run_repo.get_scoped(
            self.task.embedding_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if embedding_run is None:
            return True
        if embedding_run.status == "queued":
            if not self.task.embedding_enqueued:
                runner = get_repo_embedding_runner()
                await runner.enqueue(embedding_run.id)
                self.task.embedding_enqueued = True
            return False
        self.task.embedding_enqueued = False
        return embedding_run.status == "failed"

    async def _advance_repo_manager_stage(
        self,
        *,
        source_run: RepoRunRecord,
        file_summary_run: RepoFileSummaryRunRecord,
    ) -> bool:
        if self.task.repo_manager_run_id is None:
            if not self.task.force_rerepo_manager:
                completed = await self.group_summary_run_repo.latest_for_source_file_summary(
                    source_run_id=source_run.id,
                    source_file_summary_run_id=file_summary_run.id,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                    statuses=["completed"],
                )
                if completed is not None:
                    self.task.repo_manager_run_id = completed.id
                    self.task.repo_manager_enqueued = False
                    return False

            active = await self.group_summary_run_repo.latest_for_source_file_summary(
                source_run_id=source_run.id,
                source_file_summary_run_id=file_summary_run.id,
                tenant_id=self.task.tenant_id,
                user_id=self.task.user_id,
                statuses=["queued", "in_progress"],
            )
            if active is not None:
                self.task.repo_manager_run_id = active.id
                self.task.repo_manager_enqueued = False
            else:
                service = RepoKnowledgeRepoManagerService(
                    self.session,
                    tenant_id=self.task.tenant_id,
                    user_id=self.task.user_id,
                )
                try:
                    created = await service.create_repo_manager_run(
                        RepoManagerRunCreateRequest(
                            source_file_summary_run_id=file_summary_run.id,
                            force_rerepo_manager=self.task.force_rerepo_manager,
                        )
                    )
                except RepoManagerError:
                    logger.exception(
                        "Pipeline repo-manager stage failed to create run source_run_id=%s file_summary_run_id=%s",
                        source_run.id,
                        file_summary_run.id,
                    )
                    return True
                await self.session.commit()
                self.task.repo_manager_run_id = created.id
                self.task.repo_manager_enqueued = False

        repo_manager_run = await self.group_summary_run_repo.get_scoped(
            self.task.repo_manager_run_id,
            tenant_id=self.task.tenant_id,
            user_id=self.task.user_id,
        )
        if repo_manager_run is None:
            return True
        if repo_manager_run.status == "queued":
            if not self.task.repo_manager_enqueued:
                runner = get_repo_manager_runner()
                await runner.enqueue(repo_manager_run.id)
                self.task.repo_manager_enqueued = True
            return False
        self.task.repo_manager_enqueued = False
        return repo_manager_run.status == "failed"


def _resolve_pipeline_status(
    *,
    source_run: RepoRunRecord,
    file_summary_run: RepoFileSummaryRunRecord | None,
    repo_full_summary_run: RepoFullSummaryRunRecord | None,
    embedding_run: RepoEmbeddingRunRecord | None,
    repo_manager_run: RepoGroupSummaryRunRecord | None = None,
    group_summary_run: RepoGroupSummaryRunRecord | None = None,
) -> tuple[PipelineStatus, PipelineStage, str | None, str | None]:
    """Resolve aggregate pipeline status/stage from existing stage run rows."""

    if repo_manager_run is None:
        repo_manager_run = group_summary_run

    source_status = source_run.status
    if source_status == "queued":
        return "queued", "ingestion", None, None
    if source_status == "in_progress":
        return "in_progress", "ingestion", None, None
    if source_status == "failed":
        return "failed", "failed", source_run.error_message, source_run.error_message

    if file_summary_run is None:
        return "in_progress", "file_summary", None, None
    if file_summary_run.status in {"queued", "in_progress"}:
        return "in_progress", "file_summary", None, None
    if file_summary_run.status == "failed":
        return "failed", "failed", file_summary_run.error_message, file_summary_run.error_message

    if repo_full_summary_run is None:
        return "in_progress", "repo_full_summary", None, None
    if repo_full_summary_run.status in {"queued", "in_progress"}:
        return "in_progress", "repo_full_summary", None, None
    if repo_full_summary_run.status == "failed":
        return "failed", "failed", repo_full_summary_run.error_message, repo_full_summary_run.error_message

    if embedding_run is None:
        return "in_progress", "embedding", None, None
    if embedding_run.status in {"queued", "in_progress"}:
        return "in_progress", "embedding", None, None
    if embedding_run.status == "failed":
        return "failed", "failed", embedding_run.error_message, embedding_run.error_message

    if repo_manager_run is None:
        return "in_progress", "repo_manager", None, None
    if repo_manager_run.status == "queued":
        return "in_progress", "repo_manager", None, None
    if repo_manager_run.status == "in_progress":
        if repo_manager_run.groups_seen <= 0:
            return "in_progress", "repo_manager", None, None
        return "in_progress", "architecture", None, None
    if repo_manager_run.status == "failed":
        return "failed", "failed", repo_manager_run.error_message, repo_manager_run.error_message
    return "completed", "completed", None, None
