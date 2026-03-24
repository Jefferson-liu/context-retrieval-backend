from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from routers.scope import get_scope
from schemas import DataResponse, BulkDataResponse
from services.data_service import DataService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> DataResponse:
    try:
        raw = await file.read()
        body = raw.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to read or decode file")

    title = file.filename or "document"
    if not body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File content is empty")

    service = DataService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    try:
        record = await service.create_record(title=title, body=body, chunking=True)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {exc}")
    return DataResponse(**record)


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def upload_documents_bulk(
    response: Response,
    files: list[UploadFile] = File(...),
    scope=Depends(get_scope),
    session: AsyncSession = Depends(get_session),
) -> BulkDataResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    decoded_files: list[tuple[str, str]] = []
    for file in files:
        try:
            raw = await file.read()
            body = raw.decode("utf-8")
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to read or decode file: {file.filename}")
        title = file.filename or "document"
        if not body.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File content is empty: {title}")
        decoded_files.append((title, body))

    service = DataService(
        session,
        tenant_id=scope["tenant_id"],
        user_id=scope["user_id"],
    )
    result = await service.create_records_bulk(decoded_files, chunking=True)

    successes = [DataResponse(**r) for r in result["successes"]]
    errors = result["errors"]

    if response:
        if not successes and errors:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif errors:
            response.status_code = status.HTTP_207_MULTI_STATUS
        else:
            response.status_code = status.HTTP_201_CREATED

    return BulkDataResponse(successes=successes, errors=errors)
