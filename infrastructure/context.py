from __future__ import annotations

from dataclasses import dataclass
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ContextScope:
    tenant_id: int
    project_ids: List[int]
    user_id: str

    def primary_project(self) -> int:
        if not self.project_ids:
            raise ValueError("ContextScope.project_ids cannot be empty")
        return self.project_ids[0]


@dataclass
class RequestContextBundle:
    db: "AsyncSession"
    scope: ContextScope
