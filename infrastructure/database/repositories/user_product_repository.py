from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.user_product import UserProduct


class UserProductRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_external_id(
        self,
        *,
        tenant_id: int,
        external_id: str,
    ) -> Optional[UserProduct]:
        stmt = select(UserProduct).where(
            UserProduct.external_id == external_id,
            UserProduct.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_product(
        self,
        *,
        tenant_id: int,
        project_id: int,
        owner_external_id: str,
        external_id: str,
        name: Optional[str],
    ) -> UserProduct:
        product = UserProduct(
            tenant_id=tenant_id,
            project_id=project_id,
            owner_external_id=owner_external_id,
            external_id=external_id,
            name=name,
        )
        self.db.add(product)
        await self.db.flush()
        return product

    async def update_product(self, product: UserProduct, *, name: Optional[str]) -> UserProduct:
        if name is not None and name != product.name:
            product.name = name
            await self.db.flush()
        return product

    async def get_by_project_id(
        self,
        *,
        tenant_id: int,
        project_id: int,
    ) -> Optional[UserProduct]:
        stmt = select(UserProduct).where(
            UserProduct.project_id == project_id,
            UserProduct.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        tenant_id: int,
        owner_external_id: str,
    ) -> Sequence[UserProduct]:
        stmt = select(UserProduct).where(
            UserProduct.owner_external_id == owner_external_id,
            UserProduct.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
