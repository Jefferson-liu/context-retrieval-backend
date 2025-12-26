from __future__ import annotations

from fastapi import Header, HTTPException, status

from config.settings import get_settings


async def get_scope(
    scope_header: str | None = Header(None, alias="X-Scope"),
):
    """
    Resolve scope from a single X-Scope header ("tenant_id:user_id").
    Falls back to placeholders when enabled in settings.
    """
    settings = get_settings()

    resolved_tenant: str | None = None
    resolved_user: str | None = None

    if scope_header and (":" in scope_header):
        parts = scope_header.split(":", 1)
        resolved_tenant = parts[0].strip()
        resolved_user = parts[1].strip()

    if settings.USE_PLACEHOLDER_SCOPE:
        resolved_tenant = resolved_tenant or settings.DEFAULT_TENANT_ID
        resolved_user = resolved_user or settings.DEFAULT_USER_ID

    if not resolved_tenant or not resolved_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant/user scope (provide X-Scope as 'tenant:user')",
        )

    return {"tenant_id": resolved_tenant, "user_id": resolved_user}
