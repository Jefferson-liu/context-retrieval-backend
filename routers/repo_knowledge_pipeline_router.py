from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    RepoPipelineRunCreateRequest,
    RepoPipelineRunCreateResponse,
    RepoPipelineRunStatusResponse,
)
from services.repo_knowledge.pipeline_background_runner import get_repo_pipeline_runner
from services.repo_knowledge.pipeline_service import RepoKnowledgePipelineService, RepoPipelineError

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledgePipeline"])


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
        queued_at=snapshot.source_run.queued_at,
        started_at=snapshot.source_run.started_at,
        finished_at=snapshot.source_run.finished_at,
    )
