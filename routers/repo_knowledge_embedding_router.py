from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import (
    RepoContextPackItemResponse,
    RepoContextPackRequest,
    RepoContextPackResponse,
    RepoContextNeighborResponse,
    RepoContextSymbolHintResponse,
    RepoEmbeddingItemListResponse,
    RepoEmbeddingItemResponse,
    RepoEmbeddingRunCreateRequest,
    RepoEmbeddingRunCreateResponse,
    RepoEmbeddingRunStatusResponse,
)
from services.repo_knowledge.embedding_background_runner import get_repo_embedding_runner
from services.repo_knowledge.embedding_service import RepoEmbeddingError, RepoKnowledgeEmbeddingService
from services.repo_knowledge.retrieval.context_pack_service import RepoContextPackError, RepoContextPackService

router = APIRouter(prefix="/repo-knowledge", tags=["RepoKnowledgeEmbedding"])


@router.post("/embedding-runs", status_code=status.HTTP_202_ACCEPTED)
async def create_embedding_run(
    payload: RepoEmbeddingRunCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoEmbeddingRunCreateResponse:
    service = RepoKnowledgeEmbeddingService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        run = await service.create_embedding_run(payload)
        await session.commit()
        if run.status == "queued":
            runner = get_repo_embedding_runner()
            await runner.enqueue(run.id)
        return RepoEmbeddingRunCreateResponse(
            embedding_run_id=run.id,
            status=run.status,
            queued_at=run.queued_at,
        )
    except RepoEmbeddingError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/embedding-runs/{embedding_run_id}")
async def get_embedding_run_status(
    embedding_run_id: str,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoEmbeddingRunStatusResponse:
    service = RepoKnowledgeEmbeddingService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run = await service.get_embedding_run_status(embedding_run_id=embedding_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding run not found")
    return RepoEmbeddingRunStatusResponse(
        embedding_run_id=run.id,
        source_run_id=run.source_run_id,
        source_file_summary_run_id=run.source_file_summary_run_id,
        status=run.status,
        subjects_seen=run.subjects_seen,
        subjects_embedded=run.subjects_embedded,
        subjects_failed=run.subjects_failed,
        error_message=run.error_message,
        queued_at=run.queued_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/embedding-runs/{embedding_run_id}/items")
async def list_embedding_items(
    embedding_run_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    kind: str | None = Query(default=None),
    language: str | None = Query(default=None),
    subject_path_prefix: str | None = Query(default=None),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoEmbeddingItemListResponse:
    service = RepoKnowledgeEmbeddingService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    run, rows = await service.list_embedding_items(
        embedding_run_id=embedding_run_id,
        kind=kind,
        language=language,
        subject_path_prefix=subject_path_prefix,
        limit=limit,
        offset=offset,
    )
    if run is None or rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding run not found")

    return RepoEmbeddingItemListResponse(
        items=[
            RepoEmbeddingItemResponse(
                embedding_run_id=row.embedding_run_id,
                source_run_id=row.source_run_id,
                source_file_summary_run_id=row.source_file_summary_run_id,
                subject_id=subject.id,
                subject_path=subject.subject_path,
                language=subject.language,
                kind=row.kind,
                text_hash=row.text_hash,
                embedding_dims=row.embedding_dims,
                updated_at=row.updated_at,
            )
            for row, subject, _snapshot in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.post("/runs/{run_id}/context-pack")
async def build_context_pack(
    run_id: str,
    payload: RepoContextPackRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> RepoContextPackResponse:
    service = RepoContextPackService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        data = await service.build_context_pack(
            source_run_id=run_id,
            query=payload.query,
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
            neighbor_limit_each_direction=payload.neighbor_limit_each_direction,
        )
    except RepoContextPackError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail)

    return RepoContextPackResponse(
        source_run_id=data["source_run_id"],
        embedding_run_id=data["embedding_run_id"],
        file_summary_run_id=data["file_summary_run_id"],
        query=data["query"],
        repo_brief=data["repo_brief"],
        rerank_applied=data["rerank_applied"],
        items=[
            RepoContextPackItemResponse(
                subject_id=item.candidate.subject_id,
                subject_path=item.candidate.subject_path,
                language=item.candidate.language,
                parse_status=item.candidate.parse_status,
                overall_summary=item.candidate.overall_summary,
                file_cluster=item.candidate.file_cluster,
                important_relationships=item.candidate.important_relationships,
                group_function=item.candidate.group_function,
                similarity_score=item.candidate.similarity_score,
                rerank_score=item.rerank_score,
                final_score=item.final_score,
                rerank_reason=item.rerank_reason,
                neighbors=[
                    RepoContextNeighborResponse(
                        direction=neighbor["direction"],
                        edge_type=neighbor["edge_type"],
                        related_subject_path=neighbor["related_subject_path"],
                        related_subject_type=neighbor["related_subject_type"],
                        line=neighbor.get("line"),
                        column=neighbor.get("column"),
                    )
                    for neighbor in item.neighbors
                ],
                symbol_hints=[
                    RepoContextSymbolHintResponse(
                        symbol_name=hint["symbol_name"],
                        symbol_qualname=hint["symbol_qualname"],
                        relationships=list(hint.get("relationships") or []),
                    )
                    for hint in item.symbol_hints
                ],
            )
            for item in data["items"]
        ],
    )
