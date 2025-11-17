from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope, RequestContextBundle
from infrastructure.database.database import get_db
from infrastructure.database.repositories.user_project_role_repository import (
    UserProjectRoleRepository,
)
from infrastructure.database.repositories.user_product_repository import UserProductRepository
from infrastructure.database.models.tenancy import Project, Tenant
from infrastructure.database.setup import (
    DEFAULT_PROJECT_SLUG,
    DEFAULT_TENANT_SLUG,
    DEFAULT_USER_ID,
)
from config import settings
import hmac


def _projects_to_csv(project_ids: List[int]) -> str:
    return ",".join(str(pid) for pid in project_ids)


async def get_request_context_bundle(
    db: AsyncSession = Depends(get_db),
    user_id_header: Optional[str] = Header(None, alias="user_id"),
    project_id_header: Optional[str] = Header(None, alias="project_id"),
) -> RequestContextBundle:
    dev_bundle = await _maybe_dev_context_bundle(db, user_id_header, project_id_header)
    if dev_bundle:
        return dev_bundle
    return await _resolve_context(
        db=db,
        user_id_header=user_id_header,
        project_id_header=project_id_header,
        allow_missing_roles=False,
    )


async def get_admin_context_bundle(
    db: AsyncSession = Depends(get_db),
    user_id_header: Optional[str] = Header(None, alias="user_id"),
    project_id_header: Optional[str] = Header(None, alias="project_id"),
) -> RequestContextBundle:
    dev_bundle = await _maybe_dev_context_bundle(db, user_id_header, project_id_header)
    if dev_bundle:
        return dev_bundle
    return await _resolve_context(
        db=db,
        user_id_header=user_id_header,
        project_id_header=project_id_header,
        allow_missing_roles=True,
    )


async def _resolve_context(
    *,
    db: AsyncSession,
    user_id_header: Optional[str],
    project_id_header: Optional[str],
    allow_missing_roles: bool,
) -> RequestContextBundle:
    if user_id_header:
        user_id = user_id_header.strip()
    elif allow_missing_roles:
        user_id = DEFAULT_USER_ID
    else:
        raise HTTPException(status_code=400, detail="user_id header is required")

    project_filter: Optional[int] = None
    if project_id_header:
        try:
            project_filter = int(project_id_header)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid project identifier") from exc
    elif not allow_missing_roles:
        raise HTTPException(status_code=400, detail="project_id header is required")

    role_repo = UserProjectRoleRepository(db)
    roles = await role_repo.list_roles_for_user(user_id)

    if not roles:
        if not allow_missing_roles:
            raise HTTPException(status_code=403, detail="No project access configured for user")

        tenant_stmt = await db.execute(
            select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG)
        )
        tenant_obj = tenant_stmt.scalar_one_or_none()
        project_obj = None
        if tenant_obj:
            project_stmt = await db.execute(
                select(Project).where(
                    Project.tenant_id == tenant_obj.id,
                    Project.slug == DEFAULT_PROJECT_SLUG,
                )
            )
            project_obj = project_stmt.scalar_one_or_none()

        if not tenant_obj or not project_obj:
            raise HTTPException(
                status_code=500,
                detail="Default tenant/project not configured",
            )

        tenant_id = tenant_obj.id
        project_ids = [project_obj.id]

        await db.execute(
            text("SELECT set_app_context(:tenant_id, :project_ids)"),
            {
                "tenant_id": tenant_id,
                "project_ids": _projects_to_csv(project_ids),
            },
        )

        scope = ContextScope(tenant_id=tenant_id, project_ids=project_ids, user_id=user_id)
        return RequestContextBundle(db=db, scope=scope)

    tenant_ids = {role.tenant_id for role in roles}
    if len(tenant_ids) != 1:
        raise HTTPException(status_code=400, detail="User must belong to exactly one tenant")

    tenant_id = tenant_ids.pop()

    if project_filter is not None:
        if not any(role.project_id == project_filter for role in roles):
            raise HTTPException(status_code=403, detail="User is not assigned to the requested project")
        project_ids = [project_filter]
    else:
        project_ids = list({role.project_id for role in roles})

    product_repo = UserProductRepository(db)

    if not allow_missing_roles:
        for project_id in project_ids:
            product = await product_repo.get_by_project_id(tenant_id=tenant_id, project_id=project_id)
            if product:
                if product.owner_external_id != user_id:
                    raise HTTPException(status_code=403, detail="Product is owned by another user")
                continue

    await db.execute(
        text("SELECT set_app_context(:tenant_id, :project_ids)"),
        {
            "tenant_id": tenant_id,
            "project_ids": _projects_to_csv(project_ids),
        },
    )

    scope = ContextScope(tenant_id=tenant_id, project_ids=project_ids, user_id=user_id)
    return RequestContextBundle(db=db, scope=scope)


async def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    expected_raw = settings.API_AUTH_TOKEN
    expected = expected_raw.strip().strip('"') if expected_raw else ""
    if not expected:
        # No API key configured; allow all requests.
        return
    provided = x_api_key.strip().strip('"') if x_api_key else ""
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def _maybe_dev_context_bundle(
    db: AsyncSession,
    user_id_header: Optional[str],
    project_id_header: Optional[str],
) -> Optional[RequestContextBundle]:
    if not settings.IS_DEV_MODE:
        return None

    normalized_user = user_id_header.strip() if user_id_header else None
    if normalized_user and normalized_user != settings.DEV_PLACEHOLDER_USER_ID:
        return None

    if project_id_header:
        return None

    from services.dev.placeholders import DevPlaceholderBootstrapper

    bootstrapper = DevPlaceholderBootstrapper(db)
    return await bootstrapper.build_context_bundle()
