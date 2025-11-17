from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.tenancy import Project
from infrastructure.database.models.user_product import UserProduct
from infrastructure.database.repositories.user_product_repository import UserProductRepository
from infrastructure.database.repositories.user_project_role_repository import (
    UserProjectRoleRepository,
)
from services.user.user_directory import ExternalUser, UserDirectoryClient


class UserProductService:
    def __init__(
        self,
        db: AsyncSession,
        context: ContextScope,
        *,
        product_repository: UserProductRepository | None = None,
        role_repository: UserProjectRoleRepository | None = None,
        user_directory: UserDirectoryClient | None = None,
    ) -> None:
        self.db = db
        self.context = context
        self.product_repository = product_repository or UserProductRepository(db)
        self.role_repository = role_repository or UserProjectRoleRepository(db, context)
        self.user_directory = user_directory or UserDirectoryClient()
        self._default_role = "member"

    async def get_user_with_products(self, external_id: str) -> tuple[Optional[ExternalUser], List[UserProduct]]:
        user = await self.user_directory.fetch_user(external_id)
        if not user:
            return None, []

        products = await self.product_repository.list_for_user(
            tenant_id=self.context.tenant_id,
            owner_external_id=external_id,
        )
        return user, list(products)

    async def add_product_to_user(
        self,
        *,
        external_id: str,
        product_external_id: str,
        product_name: Optional[str],
    ) -> UserProduct:
        user = await self._ensure_remote_user(external_id)

        product = await self.product_repository.get_by_external_id(
            tenant_id=self.context.tenant_id,
            external_id=product_external_id,
        )
        if product:
            if product.owner_external_id != user.user_id:
                raise ValueError("Product is owned by another user")
            updated = await self.product_repository.update_product(product, name=product_name)
            await self._ensure_user_role(updated.project_id, user.user_id)
            return updated

        project_id = await self._create_product_project(product_external_id)
        product = await self.product_repository.create_product(
            tenant_id=self.context.tenant_id,
            project_id=project_id,
            owner_external_id=user.user_id,
            external_id=product_external_id,
            name=product_name,
        )
        await self._ensure_user_role(project_id, user.user_id)
        return product

    async def _ensure_user_role(self, project_id: int, user_external_id: str) -> None:
        await self.role_repository.ensure_role(
            user_id=user_external_id,
            tenant_id=self.context.tenant_id,
            project_id=project_id,
            role=self._default_role,
        )

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

    async def _ensure_remote_user(self, external_id: str) -> ExternalUser:
        user = await self.user_directory.fetch_user(external_id)
        if not user:
            raise ValueError(f"User '{external_id}' not found in directory")
        return user
