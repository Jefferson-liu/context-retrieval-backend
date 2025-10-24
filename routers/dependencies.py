from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.database import get_db
from infrastructure.database.models.tenancy import UserProjectRole
from infrastructure.database.setup import (
    DEFAULT_USER_ID,
)
from infrastructure.context import ContextScope, RequestContextBundle
from config import settings
import hmac


def _projects_to_csv(project_ids: List[int]) -> str:
    return ",".join(str(pid) for pid in project_ids)


async def get_request_context_bundle(
    db: AsyncSession = Depends(get_db),
) -> RequestContextBundle:
    user_id = DEFAULT_USER_ID  # Placeholder until auth pipeline supplies real users

    result = await db.execute(
        select(UserProjectRole).where(UserProjectRole.user_id == user_id)
    )
    roles = result.scalars().all()

    if not roles:
        raise HTTPException(status_code=403, detail="No project access configured for user")

    tenant_ids = {role.tenant_id for role in roles}
    if len(tenant_ids) != 1:
        raise HTTPException(status_code=400, detail="User must belong to exactly one tenant")

    tenant_id = tenant_ids.pop()
    project_ids = [role.project_id for role in roles]

    await db.execute(
        text("SELECT set_app_context(:tenant_id, :project_ids)"),
        {
            "tenant_id": tenant_id,
            "project_ids": _projects_to_csv(project_ids),
        },
    )

    scope = ContextScope(tenant_id=tenant_id, project_ids=project_ids, user_id=user_id)
    return RequestContextBundle(db=db, scope=scope)


async def require_api_key(x_api_key: Optional[str] = Header(None, convert_underscores=False)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected:
        # No API key configured; allow all requests.
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
