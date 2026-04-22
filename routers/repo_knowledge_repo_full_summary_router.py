from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    RepoFullSummaryReadmeResponse,
    RepoFullSummaryRunCreateRequest,
    RepoFullSummaryRunCreateResponse,
    RepoFullSummaryRunStatusResponse,
)
from services.repo_knowledge.repo_full_summary_background_runner import get_repo_full_summary_runner
from services.repo_knowledge.repo_full_summary_service import (
    RepoFullSummaryError,
    RepoKnowledgeRepoFullSummaryService,
)

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledgeRepoFullSummary"])


@router.post("/repo-full-summary-runs", status_code=status.HTTP_202_ACCEPTED)
async def create_repo_full_summary_run(
    payload: RepoFullSummaryRunCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFullSummaryRunCreateResponse:
    service = RepoKnowledgeRepoFullSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        run = await service.create_repo_full_summary_run(payload)
        await session.commit()
        if run.status == "queued":
            runner = get_repo_full_summary_runner()
            await runner.enqueue(run.id)
        return RepoFullSummaryRunCreateResponse(
            repo_full_summary_run_id=run.id,
            status=run.status,
            queued_at=run.queued_at,
        )
    except RepoFullSummaryError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/repo-full-summary-runs/{repo_full_summary_run_id}")
async def get_repo_full_summary_run_status(
    repo_full_summary_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFullSummaryRunStatusResponse:
    service = RepoKnowledgeRepoFullSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run = await service.get_repo_full_summary_run_status(repo_full_summary_run_id=repo_full_summary_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repo full-summary run not found")
    return RepoFullSummaryRunStatusResponse(
        repo_full_summary_run_id=run.id,
        source_run_id=run.source_run_id,
        source_file_summary_run_id=run.source_file_summary_run_id,
        status=run.status,
        prompt_version=run.prompt_version,
        files_seen=run.files_seen,
        files_used=run.files_used,
        error_message=run.error_message,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/repo-full-summary-runs/{repo_full_summary_run_id}/readme")
async def get_repo_full_summary_readme(
    repo_full_summary_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFullSummaryReadmeResponse:
    service = RepoKnowledgeRepoFullSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, readme = await service.get_repo_full_summary_readme(repo_full_summary_run_id=repo_full_summary_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repo full-summary run not found")
    if readme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repo README summary not found")
    return RepoFullSummaryReadmeResponse(
        repo_full_summary_run_id=run.id,
        source_run_id=run.source_run_id,
        source_file_summary_run_id=run.source_file_summary_run_id,
        prompt_version=run.prompt_version,
        finished_at=run.finished_at,
        readme_markdown=readme.readme_markdown,
    )


@router.get("/runs/{run_id}/repo-full-summary/latest")
async def get_latest_repo_full_summary_for_run(
    run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFullSummaryReadmeResponse:
    service = RepoKnowledgeRepoFullSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    latest_run, readme = await service.latest_repo_full_summary_for_source_run(source_run_id=run_id)
    if latest_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source run not found")
    if readme is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed repo full-summary run found")

    return RepoFullSummaryReadmeResponse(
        repo_full_summary_run_id=latest_run.id,
        source_run_id=latest_run.source_run_id,
        source_file_summary_run_id=latest_run.source_file_summary_run_id,
        prompt_version=latest_run.prompt_version,
        finished_at=latest_run.finished_at,
        readme_markdown=readme.readme_markdown,
    )
