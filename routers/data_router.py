from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from infrastructure.graphiti import get_graphiti_client
from routers.scope import get_scope
from schemas import DataListItem, DataResponse
from services.data_service import DataService

router = APIRouter(prefix="/data", tags=["Data"])


@router.get("")
async def list_data(
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> list[DataListItem]:
    graphiti_client = get_graphiti_client()
    service = DataService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
        graphiti_client=graphiti_client,
    )
    records = await service.list_records()
    return [DataListItem(**r) for r in records]


@router.get("/{data_id}")
async def get_data(
    data_id: int,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> DataResponse:
    graphiti_client = get_graphiti_client()
    service = DataService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
        graphiti_client=graphiti_client,
    )
    record = await service.get_record(data_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DataResponse(**record)


@router.delete("/{data_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data(
    data_id: int,
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
):
    graphiti_client = get_graphiti_client()
    service = DataService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
        graphiti_client=graphiti_client,
    )
    deleted = await service.delete_record(data_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.commit()
    return None
