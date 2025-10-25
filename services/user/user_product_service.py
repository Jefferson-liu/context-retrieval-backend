from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.tenancy import Project
from infrastructure.database.models.user_product import AppUser, UserProduct
from infrastructure.database.repositories.user_product_repository import (
    AppUserRepository,
    UserProductRepository,
)
from infrastructure.database.repositories.user_project_role_repository import (
    UserProjectRoleRepository,
)


class UserProductService:
    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        *,
        user_repository: AppUserRepository | None = None,
        product_repository: UserProductRepository | None = None,
        role_repository: UserProjectRoleRepository | None = None,
    ) -> None:
        self.db = db
        self.context = context
        self.user_repository = user_repository or AppUserRepository(db)
        self.product_repository = product_repository or UserProductRepository(db)
        self.role_repository = role_repository or UserProjectRoleRepository(db, context)
        self._default_role = "member"

    async def upsert_user(self, *, external_id: str, name: Optional[str] = None) -> AppUser:
        user = await self.user_repository.get_by_external_id(
            tenant_id=self.context.tenant_id,
            external_id=external_id,
        )
        if user:
            updated = await self.user_repository.update_user(user, name=name)
            await self._ensure_user_role(updated.project_id, updated.external_id)
            return updated

        project_id = await self._create_user_project(external_id)
        created = await self.user_repository.create_user(
            tenant_id=self.context.tenant_id,
            project_id=project_id,
            external_id=external_id,
            name=name,
        )
        await self._ensure_user_role(project_id, created.external_id)
        return created

    async def get_user_with_products(self, external_id: str) -> tuple[Optional[AppUser], List[UserProduct]]:
        user = await self.user_repository.get_by_external_id(
            tenant_id=self.context.tenant_id,
            external_id=external_id,
        )
        if not user:
            return None, []

        products = await self.product_repository.list_for_user(
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        return user, list(products)

    async def add_product_to_user(
        self,
        *,
        external_id: str,
        product_external_id: str,
        product_name: Optional[str],
    ) -> UserProduct:
        user = await self.user_repository.get_by_external_id(
            tenant_id=self.context.tenant_id,
            external_id=external_id,
        )
        if not user:
            user = await self.upsert_user(external_id=external_id, name=None)

        product = await self.product_repository.get_by_external_id(
            tenant_id=user.tenant_id,
            external_id=product_external_id,
        )
        if product:
            if product.user_id != user.id:
                raise ValueError("Product is owned by another user")
            updated = await self.product_repository.update_product(product, name=product_name)
            await self._ensure_user_role(updated.project_id, user.external_id)
            return updated

        project_id = await self._create_product_project(product_external_id)
        product = await self.product_repository.create_product(
            tenant_id=user.tenant_id,
            project_id=project_id,
            user_id=user.id,
            external_id=product_external_id,
            name=product_name,
        )
        await self._ensure_user_role(project_id, user.external_id)
        return product

    async def _ensure_user_role(self, project_id: int, user_external_id: str) -> None:
        await self.role_repository.ensure_role(
            user_id=user_external_id,
            tenant_id=self.context.tenant_id,
            project_id=project_id,
            role=self._default_role,
        )

    async def _create_user_project(self, external_id: str) -> int:
        base_slug = f"user-{external_id.lower().replace(' ', '-')}"
        slug = base_slug
        suffix = 1

        while True:
            stmt = select(Project).where(
                Project.tenant_id == self.context.tenant_id,
                Project.slug == slug,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                break
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        project = Project(
            tenant_id=self.context.tenant_id,
            name=f"{external_id} Base Project",
            slug=slug,
            status="active",
        )
        self.db.add(project)
        await self.db.flush()
        return project.id

    async def _create_product_project(self, product_external_id: str) -> int:
        base_slug = f"product-{product_external_id.lower().replace(' ', '-')}"
        slug = base_slug
        suffix = 1

        while True:
            stmt = select(Project).where(
                Project.tenant_id == self.context.tenant_id,
                Project.slug == slug,
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                break
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        project = Project(
            tenant_id=self.context.tenant_id,
            name=f"Product {product_external_id}",
            slug=slug,
            status="active",
        )
        self.db.add(project)
        await self.db.flush()
        return project.id
