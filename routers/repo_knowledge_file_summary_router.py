from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    RepoFileSummaryRunCreateRequest,
    RepoFileSummaryRunCreateResponse,
    RepoFileSummaryRunStatusResponse,
    RepoLatestFileSummaryResponse,
    RepoFileSummaryDiagnosticListResponse,
    RepoFileSummaryDiagnosticResponse,
    RepoFileSummaryListResponse,
    RepoFileSummaryResponse,
    RepoFileSummaryUsageItem,
    RepoFileSummaryUsageListResponse,
    RepoFileSummaryUsageSummaryResponse,
)
from services.repo_knowledge.file_summary_background_runner import get_repo_file_summary_runner
from services.repo_knowledge.file_summary_service import (
    RepoKnowledgeFileSummaryService,
    RepoFileSummaryError,
)

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledgeFileSummary"])
logger = logging.getLogger(__name__)


@router.post("/file-summary-runs", status_code=status.HTTP_202_ACCEPTED)
async def create_file_summary_run(
    payload: RepoFileSummaryRunCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSummaryRunCreateResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        run = await service.create_file_summary_run(payload)
        await session.commit()
        if run.status == "queued":
            runner = get_repo_file_summary_runner()
            await runner.enqueue(run.id)
        return RepoFileSummaryRunCreateResponse(
            file_summary_run_id=run.id,
            status=run.status,
            queued_at=run.queued_at,
        )
    except RepoFileSummaryError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/file-summary-runs/{file_summary_run_id}")
async def get_file_summary_run_status(
    file_summary_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSummaryRunStatusResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run = await service.get_file_summary_run_status(file_summary_run_id=file_summary_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File-summary run not found")
    return RepoFileSummaryRunStatusResponse(
        file_summary_run_id=run.id,
        source_run_id=run.source_run_id,
        status=run.status,
        prompt_version=run.prompt_version,
        files_seen=run.files_seen,
        files_summarized=run.files_summarized,
        files_failed=run.files_failed,
        error_message=run.error_message,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/file-summary-runs/{file_summary_run_id}/summaries")
async def list_file_summary_summaries(
    file_summary_run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    language: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    subject_path_prefix: str | None = Query(default=None),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSummaryListResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, rows = await service.list_summaries(
        file_summary_run_id=file_summary_run_id,
        limit=limit,
        offset=offset,
        language=language,
        parse_status=parse_status,
        subject_path_prefix=subject_path_prefix,
    )
    if run is None or rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File-summary run not found")

    return RepoFileSummaryListResponse(
        items=[
            RepoFileSummaryResponse(
                file_summary_run_id=summary.file_summary_run_id,
                source_run_id=summary.source_run_id,
                subject_id=subject.id,
                subject_path=subject.subject_path,
                language=subject.language,
                parse_status=snapshot.parse_status if snapshot else None,
                overall_summary=summary.overall_summary,
                file_cluster=summary.file_cluster,
                important_relationships=summary.important_relationships,
                group_function=summary.group_function,
                updated_at=summary.updated_at,
            )
            for summary, subject, snapshot in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/file-summary-runs/{file_summary_run_id}/diagnostics")
async def list_file_summary_diagnostics(
    file_summary_run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    severity: str | None = Query(default=None),
    subject_path_prefix: str | None = Query(default=None),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSummaryDiagnosticListResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, rows = await service.list_diagnostics(
        file_summary_run_id=file_summary_run_id,
        limit=limit,
        offset=offset,
        severity=severity,
        subject_path_prefix=subject_path_prefix,
    )
    if run is None or rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File-summary run not found")

    return RepoFileSummaryDiagnosticListResponse(
        items=[
            RepoFileSummaryDiagnosticResponse(
                file_summary_run_id=item.file_summary_run_id,
                source_run_id=run.source_run_id,
                subject_id=item.subject_id,
                subject_path=subject.subject_path,
                severity=item.severity,
                message=item.message,
                details=item.details,
                created_at=item.created_at,
            )
            for item, subject in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}/file-summaries/latest")
async def get_latest_summaries_for_source_run(
    run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoLatestFileSummaryResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    latest_run, rows = await service.latest_summaries_for_source_run(
        source_run_id=run_id,
        limit=limit,
        offset=offset,
    )
    if latest_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source run not found")
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed file_summary run found")

    return RepoLatestFileSummaryResponse(
        file_summary_run_id=latest_run.id,
        source_run_id=latest_run.source_run_id,
        prompt_version=latest_run.prompt_version,
        finished_at=latest_run.finished_at,
        items=[
            RepoFileSummaryResponse(
                file_summary_run_id=summary.file_summary_run_id,
                source_run_id=summary.source_run_id,
                subject_id=subject.id,
                subject_path=subject.subject_path,
                language=subject.language,
                parse_status=snapshot.parse_status if snapshot else None,
                overall_summary=summary.overall_summary,
                file_cluster=summary.file_cluster,
                important_relationships=summary.important_relationships,
                group_function=summary.group_function,
                updated_at=summary.updated_at,
            )
            for summary, subject, snapshot in rows
        ],
    )


@router.get("/file-summary-runs/{file_summary_run_id}/usage")
async def list_file_summary_usage(
    file_summary_run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    usage_status: str | None = Query(default=None, alias="status"),
    subject_path_prefix: str | None = Query(default=None),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSummaryUsageListResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, rows = await service.list_usage(
        file_summary_run_id=file_summary_run_id,
        limit=limit,
        offset=offset,
        status=usage_status,
        subject_path_prefix=subject_path_prefix,
    )
    if run is None or rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File-summary run not found")

    return RepoFileSummaryUsageListResponse(
        items=[
            RepoFileSummaryUsageItem(
                file_summary_run_id=usage.file_summary_run_id,
                subject_id=usage.subject_id,
                subject_path=subject.subject_path,
                model_provider=usage.model_provider,
                model_name=usage.model_name,
                status=usage.status,
                error_message=usage.error_message,
                total_input_tokens=usage.total_input_tokens,
                total_output_tokens=usage.total_output_tokens,
                total_tokens=usage.total_tokens,
                cached_input_tokens=usage.cached_input_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                llm_step_count=usage.llm_step_count,
                tool_call_count=usage.tool_call_count,
                duration_ms=usage.duration_ms,
                steps=usage.steps or [],
                created_at=usage.created_at,
            )
            for usage, subject in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/file-summary-runs/{file_summary_run_id}/usage/summary")
async def get_file_summary_usage_summary(
    file_summary_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSummaryUsageSummaryResponse:
    service = RepoKnowledgeFileSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, agg = await service.aggregate_usage(
        file_summary_run_id=file_summary_run_id,
    )
    if run is None or agg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File-summary run not found")

    return RepoFileSummaryUsageSummaryResponse(
        file_summary_run_id=run.id,
        file_count=agg["file_count"],
        completed_count=agg["completed_count"],
        failed_count=agg["failed_count"],
        skipped_count=agg["skipped_count"],
        total_input_tokens=agg["total_input_tokens"],
        total_output_tokens=agg["total_output_tokens"],
        total_tokens=agg["total_tokens"],
        cached_input_tokens=agg["cached_input_tokens"],
        reasoning_tokens=agg["reasoning_tokens"],
        avg_duration_ms=agg["avg_duration_ms"],
        avg_tokens_per_file=agg["avg_tokens_per_file"],
    )
