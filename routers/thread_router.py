from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from schemas import ThreadCreateRequest, ThreadIngestResponse
from services.thread_service import ThreadService
from routers.scope import get_scope

router = APIRouter(prefix="/threads", tags=["Threads"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def ingest_thread(
    payload: ThreadCreateRequest,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> ThreadIngestResponse:
    if not payload.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="messages are required")
    service = ThreadService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        record = await service.ingest_thread(messages=payload.messages)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Thread ingestion failed: {exc}")
    return ThreadIngestResponse(**record)
