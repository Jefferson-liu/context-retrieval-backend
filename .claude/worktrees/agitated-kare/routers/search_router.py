from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from infrastructure.graphiti import get_graphiti_client
from routers.scope import get_scope
from services.search_service import SearchService
from infrastructure.graphiti import build_group_id
router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    scope=Depends(get_scope),
):
    client = get_graphiti_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graphiti client unavailable",
        )
    group_id = build_group_id(scope["tenant_id"], scope["user_id"])
    service = SearchService(graphiti_client=client, group_ids=[group_id])
    try:
        results = await service.search(query=q)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Graphiti search failed: {exc}")
    return results
