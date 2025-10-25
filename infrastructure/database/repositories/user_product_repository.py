from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.user_product import AppUser, UserProduct


class AppUserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_external_id(
        self,
        *,
        tenant_id: int,
        external_id: str,
    ) -> Optional[AppUser]:
        stmt = select(AppUser).where(
            AppUser.external_id == external_id,
            AppUser.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_project_id(
        self,
        *,
        tenant_id: int,
        project_id: int,
    ) -> Optional[AppUser]:
        stmt = select(AppUser).where(
            AppUser.project_id == project_id,
            AppUser.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        *,
        tenant_id: int,
        project_id: int,
        external_id: str,
        name: Optional[str],
    ) -> AppUser:
        user = AppUser(
            tenant_id=tenant_id,
            project_id=project_id,
            external_id=external_id,
            name=name,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def update_user(self, user: AppUser, *, name: Optional[str]) -> AppUser:
        if name is not None and name != user.name:
            user.name = name
            await self.db.flush()
        return user


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
        user_id: int,
        external_id: str,
        name: Optional[str],
    ) -> UserProduct:
        product = UserProduct(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
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
        user_id: int,
    ) -> Sequence[UserProduct]:
        stmt = select(UserProduct).where(
            UserProduct.user_id == user_id,
            UserProduct.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
