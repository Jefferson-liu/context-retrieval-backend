from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class KnowledgeEntityMatch(BaseModel):
    id: int = Field(..., description="Primary key of the knowledge entity")
    name: str = Field(..., description="Entity display name")
    entity_type: str = Field(..., description="Classifier describing the entity category")
    description: Optional[str] = Field(
        None, description="Short explanation captured when the entity was created"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity confidence between the requested name and this entity",
    )


class EntityResolutionResponse(BaseModel):
    query: str = Field(..., description="Original entity text submitted for lookup")
    status: Literal["resolved", "unknown"] = Field(
        ..., description="Indicates whether any entities cleared the similarity threshold"
    )
    matches: list[KnowledgeEntityMatch] = Field(
        default_factory=list, description="Ordered list of candidate entities"
    )

