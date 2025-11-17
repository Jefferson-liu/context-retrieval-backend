from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProductCreateRequest(BaseModel):
    product_id: str = Field(..., description="External identifier for the product")
    name: Optional[str] = Field(None, description="Display name for the product")


class ProductResponse(BaseModel):
    product_id: str
    project_id: int
    name: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    name: Optional[str]
    products: List[ProductResponse] = Field(default_factory=list)
