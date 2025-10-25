from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.context import ContextScope
from infrastructure.database.models.tenancy import UserProjectRole


class UserProjectRoleRepository:
    def __init__(self, db: AsyncSession, context: ContextScope | None = None) -> None:
        self.db = db
        self.context = context

    async def list_roles_for_user(self, user_id: str) -> List[UserProjectRole]:
        stmt = select(UserProjectRole).where(UserProjectRole.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_role(self, user_id: str, project_id: int) -> Optional[UserProjectRole]:
        stmt = select(UserProjectRole).where(
            UserProjectRole.user_id == user_id,
            UserProjectRole.project_id == project_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def ensure_role(
        self,
        *,
        user_id: str,
        tenant_id: int,
        project_id: int,
        role: str = "member",
    ) -> UserProjectRole:
        existing = await self.get_role(user_id=user_id, project_id=project_id)
        if existing:
            return existing

        assignment = UserProjectRole(
            user_id=user_id,
            tenant_id=tenant_id,
            project_id=project_id,
            role=role,
        )
        self.db.add(assignment)
        await self.db.flush()
        return assignment
