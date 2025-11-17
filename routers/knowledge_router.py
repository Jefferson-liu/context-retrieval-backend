from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from infrastructure.context import RequestContextBundle
from routers.dependencies import get_request_context_bundle
from schemas import EntityResolutionResponse, KnowledgeEntityMatch
from services.knowledge import EntityResolutionService, KnowledgeGraphService
from services.text_thread.text_thread_service import TextThreadService
from schemas.requests.text_thread import UploadTextThreadRequest


class EntityResolutionRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Free-form entity text to resolve")
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of entity matches to return",
    )
    min_confidence: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Lower bound confidence for returning a match",
    )


router = APIRouter()


@router.post(
    "/knowledge/entities/resolve",
    summary="Resolve entity names against the knowledge graph",
    response_model=EntityResolutionResponse,
)
async def resolve_entity(
    request: EntityResolutionRequest,
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle),
) -> EntityResolutionResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    service = EntityResolutionService(context_bundle.db, context_bundle.scope)
    matches = await service.resolve(
        query,
        limit=request.top_k,
        min_confidence=request.min_confidence,
    )

    if not matches:
        return EntityResolutionResponse(query=request.query, status="unknown", matches=[])

    return EntityResolutionResponse(
        query=request.query,
        status="resolved",
        matches=[
            KnowledgeEntityMatch(
                id=match.id,
                name=match.name,
                entity_type=match.entity_type,
                description=match.description,
                confidence=match.confidence,
            )
            for match in matches
        ],
    )


@router.post(
    "/knowledge/event-invalidations/{batch_id}/apply",
    summary="Apply a pending event invalidation batch",
)
async def apply_event_invalidation_batch(
    batch_id: str,
    context_bundle: RequestContextBundle = Depends(get_request_context_bundle),
):
    service = KnowledgeGraphService(context_bundle.db, context_bundle.scope)
    applied = await service.apply_event_invalidation_batch(batch_id, approved_by="api")
    if not applied:
        raise HTTPException(status_code=404, detail="Batch not found or already applied")
    return {"status": "applied", "batch_id": batch_id}

