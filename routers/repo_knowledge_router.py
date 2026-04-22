from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    RepoEdgeListResponse,
    RepoEdgeResponse,
    RepoFileSnapshotListResponse,
    RepoFileSnapshotResponse,
    RepoRunCreateRequest,
    RepoRunCreateResponse,
    RepoRunListItemResponse,
    RepoRunListResponse,
    RepoRunStatusResponse,
    RepoLinkedFileSummaryRunResponse,
)
from services.repo_knowledge.background_runner import get_repo_ingestion_runner
from services.repo_knowledge.ingestion_service import RepoIngestionError, RepoKnowledgeService

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledge"])
logger = logging.getLogger(__name__)


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_repo_run(
    payload: RepoRunCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoRunCreateResponse:
    logger.info(
        "Repo run create requested tenant=%s user=%s source_type=%s source_path=%s force_reingest=%s",
        scope["tenant_id"],
        scope["user_id"],
        payload.source_type,
        payload.source_path,
        payload.force_reingest,
    )
    service = RepoKnowledgeService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        run = await service.create_run(payload)
        await session.commit()
        logger.info("Repo run created run_id=%s status=%s", run.id, run.status)
        runner = get_repo_ingestion_runner()
        await runner.enqueue(run.id, force_reingest=payload.force_reingest)
        logger.info("Repo run enqueued run_id=%s", run.id)
        return RepoRunCreateResponse(run_id=run.id, status=run.status, queued_at=run.queued_at)
    except NotImplementedError as exc:
        await session.rollback()
        logger.warning("Repo run rejected (not implemented): %s", exc)
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except RepoIngestionError as exc:
        await session.rollback()
        logger.warning("Repo run rejected (validation): %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/runs")
async def list_repo_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoRunListResponse:
    logger.debug(
        "Repo run list requested tenant=%s user=%s limit=%s offset=%s status=%s",
        scope["tenant_id"],
        scope["user_id"],
        limit,
        offset,
        status_filter,
    )
    service = RepoKnowledgeService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    runs, file_summary_runs_by_source = await service.list_runs(
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    return RepoRunListResponse(
        items=[
            RepoRunListItemResponse(
                run_id=run.id,
                status=run.status,
                source_type=run.source_type,
                repo_address=run.repo_address,
                source_locator=run.source_locator,
                queued_at=run.queued_at,
                started_at=run.started_at,
                finished_at=run.finished_at,
                file_summary_runs=[
                    RepoLinkedFileSummaryRunResponse(
                        file_summary_run_id=file_summary_run.id,
                        status=file_summary_run.status,
                        queued_at=file_summary_run.queued_at,
                        started_at=file_summary_run.started_at,
                        finished_at=file_summary_run.finished_at,
                    )
                    for file_summary_run in file_summary_runs_by_source.get(run.id, [])
                ],
            )
            for run in runs
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}")
async def get_repo_run_status(
    run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoRunStatusResponse:
    logger.debug("Repo run status requested run_id=%s", run_id)
    service = RepoKnowledgeService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run = await service.get_run_status(run_id=run_id)
    if run is None:
        logger.warning("Repo run status lookup failed run_id=%s", run_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    logger.debug("Repo run status returned run_id=%s status=%s", run_id, run.status)

    return RepoRunStatusResponse(
        run_id=run.id,
        status=run.status,
        source_type=run.source_type,
        repo_address=run.repo_address,
        source_locator=run.source_locator,
        fingerprint=run.fingerprint,
        files_seen=run.files_seen,
        files_ingested=run.files_ingested,
        files_skipped=run.files_skipped,
        chunks_written=run.chunks_written,
        parse_success_count=run.parse_success_count,
        parse_failed_count=run.parse_failed_count,
        edge_count_file=run.edge_count_file,
        edge_count_symbol=run.edge_count_symbol,
        error_message=run.error_message,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/runs/{run_id}/files")
async def list_repo_run_files(
    run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ingest_status: str | None = Query(default=None),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoFileSnapshotListResponse:
    logger.debug(
        "Repo run files requested run_id=%s limit=%s offset=%s ingest_status=%s",
        run_id,
        limit,
        offset,
        ingest_status,
    )
    service = RepoKnowledgeService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    rows = await service.list_files(
        run_id=run_id,
        limit=limit,
        offset=offset,
        ingest_status=ingest_status,
    )
    if rows is None:
        logger.warning("Repo run files lookup failed run_id=%s", run_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    logger.debug("Repo run files returned run_id=%s count=%s", run_id, len(rows))

    return RepoFileSnapshotListResponse(
        items=[
            RepoFileSnapshotResponse(
                run_id=snapshot.run_id,
                subject_id=subject.id,
                subject_path=subject.subject_path,
                subject_type=subject.subject_type,
                language=subject.language,
                size_bytes=snapshot.size_bytes,
                line_count=snapshot.line_count,
                content_hash=snapshot.content_hash,
                ingest_status=snapshot.ingest_status,
                parse_status=snapshot.parse_status,
                skip_reason=snapshot.skip_reason,
                parse_error=snapshot.parse_error,
                chunk_count=snapshot.chunk_count,
            )
            for snapshot, subject in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}/edges")
async def list_repo_run_edges(
    run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    edge_type: str | None = Query(default=None),
    from_subject_type: str | None = Query(default=None),
    to_subject_type: str | None = Query(default=None),
    language: str | None = Query(default=None),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoEdgeListResponse:
    logger.debug(
        "Repo run edges requested run_id=%s limit=%s offset=%s edge_type=%s from_type=%s to_type=%s language=%s",
        run_id,
        limit,
        offset,
        edge_type,
        from_subject_type,
        to_subject_type,
        language,
    )
    service = RepoKnowledgeService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    rows = await service.list_edges(
        run_id=run_id,
        limit=limit,
        offset=offset,
        edge_type=edge_type,
        from_subject_type=from_subject_type,
        to_subject_type=to_subject_type,
        language=language,
    )
    if rows is None:
        logger.warning("Repo run edges lookup failed run_id=%s", run_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    logger.debug("Repo run edges returned run_id=%s count=%s", run_id, len(rows))

    return RepoEdgeListResponse(
        items=[
            RepoEdgeResponse(
                run_id=edge.run_id,
                from_subject_id=edge.from_subject_id,
                to_subject_id=edge.to_subject_id,
                from_subject_type=from_subject.subject_type,
                to_subject_type=to_subject.subject_type,
                from_subject_path=from_subject.subject_path,
                to_subject_path=to_subject.subject_path,
                edge_type=edge.edge_type,
                line=edge.line,
                column=edge.column,
                evidence=edge.evidence,
                is_external_target=edge.is_external_target,
            )
            for edge, from_subject, to_subject in rows
        ],
        limit=limit,
        offset=offset,
    )
