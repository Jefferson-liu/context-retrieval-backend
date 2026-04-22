from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    PipelineStageProgress,
    RepoPipelineRunCreateRequest,
    RepoPipelineRunCreateResponse,
    RepoPipelineRunStatusResponse,
    RepoPipelineRunListResponse,
)
from services.repo_knowledge.pipeline_background_runner import get_repo_pipeline_runner
from services.repo_knowledge.pipeline_service import (
    RepoKnowledgePipelineService,
    RepoPipelineError,
    RepoPipelineStatusSnapshot,
)

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledgePipeline"])


def _resolve_stage_progress(snapshot: RepoPipelineStatusSnapshot) -> PipelineStageProgress | None:
    stage = snapshot.stage
    if stage in ("queued", "completed", "failed"):
        return None
    if stage == "ingestion":
        return PipelineStageProgress(
            items_total=snapshot.source_run.files_seen,
            items_completed=snapshot.source_run.files_ingested,
            items_failed=snapshot.source_run.files_skipped,
        )
    if stage == "file_summary" and snapshot.file_summary_run:
        return PipelineStageProgress(
            items_total=snapshot.file_summary_run.files_seen,
            items_completed=snapshot.file_summary_run.files_summarized,
            items_failed=snapshot.file_summary_run.files_failed,
        )
    if stage == "repo_full_summary":
        run = snapshot.repo_full_summary_run
        if run and run.status == "completed":
            return PipelineStageProgress(items_total=1, items_completed=1, items_failed=0)
        if run and run.status == "failed":
            return PipelineStageProgress(items_total=1, items_completed=0, items_failed=1)
        return PipelineStageProgress(items_total=1, items_completed=0, items_failed=0)
    if stage == "embedding" and snapshot.embedding_run:
        return PipelineStageProgress(
            items_total=snapshot.embedding_run.subjects_seen,
            items_completed=snapshot.embedding_run.subjects_embedded,
            items_failed=snapshot.embedding_run.subjects_failed,
        )
    if stage in ("repo_manager", "architecture") and snapshot.repo_manager_run:
        return PipelineStageProgress(
            items_total=snapshot.repo_manager_run.groups_seen,
            items_completed=snapshot.repo_manager_run.groups_summarized,
            items_failed=snapshot.repo_manager_run.groups_failed,
        )
    return None


def _snapshot_to_response(snapshot: RepoPipelineStatusSnapshot) -> RepoPipelineRunStatusResponse:
    return RepoPipelineRunStatusResponse(
        run_id=snapshot.source_run.id,
        status=snapshot.status,
        stage=snapshot.stage,
        source_type=snapshot.source_run.source_type,
        repo_address=snapshot.source_run.repo_address,
        source_locator=snapshot.source_run.source_locator,
        source_run_status=snapshot.source_run.status,
        file_summary_run_id=snapshot.file_summary_run.id if snapshot.file_summary_run else None,
        file_summary_run_status=snapshot.file_summary_run.status if snapshot.file_summary_run else None,
        repo_full_summary_run_id=snapshot.repo_full_summary_run.id if snapshot.repo_full_summary_run else None,
        repo_full_summary_run_status=snapshot.repo_full_summary_run.status if snapshot.repo_full_summary_run else None,
        embedding_run_id=snapshot.embedding_run.id if snapshot.embedding_run else None,
        embedding_run_status=snapshot.embedding_run.status if snapshot.embedding_run else None,
        repo_manager_run_id=snapshot.repo_manager_run.id if snapshot.repo_manager_run else None,
        repo_manager_run_status=snapshot.repo_manager_run.status if snapshot.repo_manager_run else None,
        error_message=snapshot.error_message,
        stage_error_message=snapshot.stage_error_message,
        files_seen=snapshot.source_run.files_seen,
        files_ingested=snapshot.source_run.files_ingested,
        stage_progress=_resolve_stage_progress(snapshot),
        queued_at=snapshot.source_run.queued_at,
        started_at=snapshot.source_run.started_at,
        finished_at=snapshot.source_run.finished_at,
    )


@router.post("/pipeline-runs", status_code=status.HTTP_202_ACCEPTED)
async def create_pipeline_run(
    payload: RepoPipelineRunCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoPipelineRunCreateResponse:
    service = RepoKnowledgePipelineService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        source_run, queue_item = await service.create_pipeline_run(payload)
        await session.commit()

        pipeline_runner = get_repo_pipeline_runner()
        await pipeline_runner.enqueue(queue_item)
        return RepoPipelineRunCreateResponse(
            run_id=source_run.id,
            status="queued",
            stage="ingestion",
            file_summary_run_id=None,
            repo_full_summary_run_id=None,
            embedding_run_id=None,
            repo_manager_run_id=None,
            queued_at=source_run.queued_at,
        )
    except RepoPipelineError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/pipeline-runs")
async def list_pipeline_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoPipelineRunListResponse:
    service = RepoKnowledgePipelineService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    snapshots = await service.list_pipeline_statuses(
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    return RepoPipelineRunListResponse(
        items=[_snapshot_to_response(s) for s in snapshots],
        limit=limit,
        offset=offset,
    )


@router.get("/pipeline-runs/{run_id}")
async def get_pipeline_run_status(
    run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoPipelineRunStatusResponse:
    service = RepoKnowledgePipelineService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    snapshot = await service.get_pipeline_status(source_run_id=run_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return _snapshot_to_response(snapshot)
