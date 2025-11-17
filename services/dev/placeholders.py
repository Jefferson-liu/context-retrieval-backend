from __future__ import annotations

from typing import List

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from infrastructure.context import ContextScope, RequestContextBundle
from infrastructure.database.models.tenancy import Project, Tenant, UserProjectRole
from infrastructure.database.models.user_product import UserProduct
from infrastructure.database.setup import DEFAULT_TENANT_SLUG


class DevPlaceholderBootstrapper:
    """Creates a default user/product/project for local development mode."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_context_bundle(self) -> RequestContextBundle:
        scope = await self._ensure_scope()
        return RequestContextBundle(db=self.db, scope=scope)

    async def _ensure_scope(self) -> ContextScope:
        tenant = await self._get_default_tenant()
        project = await self._get_or_create_project(tenant.id)
        await self._ensure_user_role(tenant.id, project.id)
        await self._set_context(tenant.id, [project.id])
        await self._ensure_product(tenant.id, project.id)
        return ContextScope(
            tenant_id=tenant.id,
            project_ids=[project.id],
            user_id=settings.DEV_PLACEHOLDER_USER_ID,
        )

    async def _get_default_tenant(self) -> Tenant:
        stmt = select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG)
        result = await self.db.execute(stmt)
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant
        raise RuntimeError("Default tenant not found; run database seed before dev mode")

    async def _get_or_create_project(self, tenant_id: int) -> Project:
        stmt = select(Project).where(
            Project.tenant_id == tenant_id,
            Project.slug == settings.DEV_PLACEHOLDER_PROJECT_SLUG,
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if project:
            return project

        project = Project(
            tenant_id=tenant_id,
            name=settings.DEV_PLACEHOLDER_PRODUCT_NAME,
            slug=settings.DEV_PLACEHOLDER_PROJECT_SLUG,
            status="active",
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def _ensure_user_role(self, tenant_id: int, project_id: int) -> None:
        stmt = select(UserProjectRole).where(
            UserProjectRole.user_id == settings.DEV_PLACEHOLDER_USER_ID,
            UserProjectRole.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return

        assignment = UserProjectRole(
            user_id=settings.DEV_PLACEHOLDER_USER_ID,
            tenant_id=tenant_id,
            project_id=project_id,
            role="member",
        )
        self.db.add(assignment)
        await self.db.flush()

    async def _ensure_product(self, tenant_id: int, project_id: int) -> None:
        stmt = select(UserProduct).where(
            UserProduct.tenant_id == tenant_id,
            UserProduct.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return

        product = UserProduct(
            tenant_id=tenant_id,
            project_id=project_id,
            owner_external_id=settings.DEV_PLACEHOLDER_USER_ID,
            external_id=settings.DEV_PLACEHOLDER_PRODUCT_ID,
            name=settings.DEV_PLACEHOLDER_PRODUCT_NAME,
        )
        self.db.add(product)
        await self.db.flush()

    async def _set_context(self, tenant_id: int, project_ids: List[int]) -> None:
        await self.db.execute(
            text("SELECT set_app_context(:tenant_id, :project_ids)"),
            {
                "tenant_id": tenant_id,
                "project_ids": ",".join(str(pid) for pid in project_ids),
            },
        )
