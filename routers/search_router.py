from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Graph search has been removed. Use repo-knowledge context retrieval instead.",
    )
