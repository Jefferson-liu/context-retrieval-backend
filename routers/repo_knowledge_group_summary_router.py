from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    RepoGroupSummaryArchitectureResponse,
    RepoGroupSummaryItemListResponse,
    RepoGroupSummaryItemResponse,
    RepoGroupSummaryMemberResponse,
    RepoGroupSummaryRunCreateRequest,
    RepoGroupSummaryRunCreateResponse,
    RepoGroupSummaryRunStatusResponse,
    RepoLatestGroupSummaryResponse,
)
from services.repo_knowledge.group_summary_background_runner import get_repo_group_summary_runner
from services.repo_knowledge.group_summary_service import RepoGroupSummaryError, RepoKnowledgeGroupSummaryService

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledgeGroupSummary"])


@router.post("/group-summary-runs", status_code=status.HTTP_202_ACCEPTED)
async def create_group_summary_run(
    payload: RepoGroupSummaryRunCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoGroupSummaryRunCreateResponse:
    service = RepoKnowledgeGroupSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        run = await service.create_group_summary_run(payload)
        await session.commit()
        if run.status == "queued":
            runner = get_repo_group_summary_runner()
            await runner.enqueue(run.id)
        return RepoGroupSummaryRunCreateResponse(
            group_summary_run_id=run.id,
            status=run.status,
            queued_at=run.queued_at,
        )
    except RepoGroupSummaryError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/group-summary-runs/{group_summary_run_id}")
async def get_group_summary_run_status(
    group_summary_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoGroupSummaryRunStatusResponse:
    service = RepoKnowledgeGroupSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run = await service.get_group_summary_run_status(group_summary_run_id=group_summary_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group-summary run not found")

    return RepoGroupSummaryRunStatusResponse(
        group_summary_run_id=run.id,
        source_run_id=run.source_run_id,
        source_file_summary_run_id=run.source_file_summary_run_id,
        status=run.status,
        prompt_version=run.prompt_version,
        groups_seen=run.groups_seen,
        groups_summarized=run.groups_summarized,
        groups_failed=run.groups_failed,
        members_seen=run.members_seen,
        architecture_overview=run.architecture_overview,
        merged_mermaid_diagram_available=bool(run.merged_mermaid_diagram),
        error_message=run.error_message,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/group-summary-runs/{group_summary_run_id}/architecture")
async def get_group_summary_architecture(
    group_summary_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoGroupSummaryArchitectureResponse:
    service = RepoKnowledgeGroupSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run = await service.get_architecture_artifact(group_summary_run_id=group_summary_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merged architecture not found")

    return RepoGroupSummaryArchitectureResponse(
        group_summary_run_id=run.id,
        source_run_id=run.source_run_id,
        source_file_summary_run_id=run.source_file_summary_run_id,
        prompt_version=run.prompt_version,
        architecture_overview=run.architecture_overview or "",
        mermaid_diagram=run.merged_mermaid_diagram or "",
        finished_at=run.finished_at,
    )


@router.get("/group-summary-runs/{group_summary_run_id}/groups")
async def list_group_summary_groups(
    group_summary_run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    layer_hint: str | None = Query(default=None),
    is_infrastructure: bool | None = Query(default=None),
    group_key_prefix: str | None = Query(default=None),
    include_members: bool = Query(default=False),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoGroupSummaryItemListResponse:
    service = RepoKnowledgeGroupSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, rows, member_map = await service.list_group_summaries(
        group_summary_run_id=group_summary_run_id,
        limit=limit,
        offset=offset,
        layer_hint=layer_hint,
        is_infrastructure=is_infrastructure,
        group_key_prefix=group_key_prefix,
        include_members=include_members,
    )
    if run is None or rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group-summary run not found")

    return RepoGroupSummaryItemListResponse(
        items=[
            _serialize_group_item(group=group, summary=summary, members=(member_map or {}).get(group.group_id, []))
            for group, summary in rows
        ],
        limit=limit,
        offset=offset,
        include_members=include_members,
    )


@router.get("/runs/{run_id}/group-summaries/latest")
async def get_latest_group_summaries_for_run(
    run_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_members: bool = Query(default=False),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoLatestGroupSummaryResponse:
    service = RepoKnowledgeGroupSummaryService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    latest_run, rows, member_map = await service.latest_group_summaries_for_source_run(
        source_run_id=run_id,
        limit=limit,
        offset=offset,
        include_members=include_members,
    )
    if latest_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source run not found")
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed group-summary run found")

    return RepoLatestGroupSummaryResponse(
        group_summary_run_id=latest_run.id,
        source_run_id=latest_run.source_run_id,
        source_file_summary_run_id=latest_run.source_file_summary_run_id,
        prompt_version=latest_run.prompt_version,
        finished_at=latest_run.finished_at,
        include_members=include_members,
        items=[
            _serialize_group_item(group=group, summary=summary, members=(member_map or {}).get(group.group_id, []))
            for group, summary in rows
        ],
    )


def _serialize_group_item(*, group, summary, members) -> RepoGroupSummaryItemResponse:  # noqa: ANN001
    return RepoGroupSummaryItemResponse(
        group_id=group.group_id,
        group_key=group.group_key,
        group_label=group.group_label,
        layer_hint=group.layer_hint,
        member_count=group.member_count,
        dependency_neighbor_count=group.dependency_neighbor_count,
        is_infrastructure_seed=group.is_infrastructure_seed,
        heuristics=group.heuristics,
        name=summary.name if summary else None,
        overall_summary=summary.overall_summary if summary else None,
        business_purpose=summary.business_purpose if summary else None,
        responsibilities=list(summary.responsibilities or []) if summary else [],
        tags=list(summary.tags or []) if summary else [],
        representative_subject_ids=list(summary.representative_subject_ids or []) if summary else [],
        mermaid_diagram=summary.mermaid_diagram if summary else None,
        is_infrastructure=summary.is_infrastructure if summary else None,
        confidence=float(summary.confidence) if summary else None,
        updated_at=summary.updated_at if summary else None,
        members=[
            RepoGroupSummaryMemberResponse(
                subject_id=subject.id,
                subject_path=subject.subject_path,
                language=subject.language,
                rank=member.rank,
                is_representative=member.is_representative,
                membership_reason=member.membership_reason,
            )
            for member, subject in members
        ],
    )
