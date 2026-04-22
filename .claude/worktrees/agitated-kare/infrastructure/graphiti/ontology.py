from __future__ import annotations

from datetime import datetime
from typing import Dict, Mapping, Sequence, Tuple, Type

from pydantic import BaseModel, Field


class Product(BaseModel):
    category: str | None = Field(None, description="Product category or domain")
    status: str | None = Field(None, description="Lifecycle status")
    launch_date: datetime | None = Field(None, description="Initial launch or planned date")
    owner: str | None = Field(None, description="Primary owner (name or team)")
    org: str | None = Field(None, description="Org or business unit")


class Feature(BaseModel):
    product: str | None = Field(None, description="Parent product name")
    status: str | None = Field(None, description="Lifecycle status")
    priority: str | None = Field(None, description="Priority or tier")
    area: str | None = Field(None, description="Domain area")
    release_version: str | None = Field(None, description="Target or actual release version")


class Decision(BaseModel):
    topic: str | None = Field(None, description="Decision topic")
    status: str | None = Field(None, description="Status (proposed/approved/rejected)")
    decision_date: datetime | None = Field(None, description="Decision date")
    owner: str | None = Field(None, description="Decision maker")
    rationale: str | None = Field(None, description="Short rationale")


class Issue(BaseModel):
    severity: str | None = Field(None, description="Severity")
    status: str | None = Field(None, description="Status (open/in-progress/resolved)")
    impact: str | None = Field(None, description="Impact description")


class Release(BaseModel):
    version: str | None = Field(None, description="Release version or tag")
    status: str | None = Field(None, description="Status (planned/shipped)")
    release_date: datetime | None = Field(None, description="Target or actual date")
    scope: str | None = Field(None, description="Scope summary")


class Person(BaseModel):
    role: str | None = Field(None, description="Role/title")
    team: str | None = Field(None, description="Team or squad")
    org: str | None = Field(None, description="Org or business unit")
    email: str | None = Field(None, description="Contact email")


class Team(BaseModel):
    function: str | None = Field(None, description="Team function/domain")
    org: str | None = Field(None, description="Org or business unit")
    lead: str | None = Field(None, description="Team lead/manager")


class Component(BaseModel):
    layer: str | None = Field(None, description="Layer (frontend/backend/infra)")
    owner: str | None = Field(None, description="Owner team/person")
    status: str | None = Field(None, description="Status")


class WorksOn(BaseModel):
    role: str | None = Field(None, description="Role or responsibility")
    start_date: datetime | None = Field(None, description="Start date")
    end_date: datetime | None = Field(None, description="End date")


class Owns(BaseModel):
    owner_type: str | None = Field(None, description="Owner type (team/person)")
    start_date: datetime | None = Field(None, description="Ownership start")
    end_date: datetime | None = Field(None, description="Ownership end")


class DependsOn(BaseModel):
    dependency_type: str | None = Field(None, description="Type (tech/process/external)")
    risk: str | None = Field(None, description="Risk/impact")
    notes: str | None = Field(None, description="Additional context")


class Implements(BaseModel):
    status: str | None = Field(None, description="Status (planned/in-progress/shipped)")
    target_version: str | None = Field(None, description="Target release/version")


class Blocks(BaseModel):
    impact: str | None = Field(None, description="Impact description")
    severity: str | None = Field(None, description="Severity")
    status: str | None = Field(None, description="Blocker status")


class Decides(BaseModel):
    decision_date: datetime | None = Field(None, description="Decision date")
    status: str | None = Field(None, description="Status (approved/rejected/proposed)")


class Mentions(BaseModel):
    context_type: str | None = Field(None, description="Context (slack, doc, note)")
    source: str | None = Field(None, description="Source identifier or URL")


class HasFeature(BaseModel):
    status: str | None = Field(None, description="Status/context of the feature relationship")
    notes: str | None = Field(None, description="Additional context or rationale")


DEFAULT_ENTITY_TYPES: Dict[str, Type[BaseModel]] = {
    "Product": Product,
    "Feature": Feature,
    "Decision": Decision,
    "Issue": Issue,
    "Release": Release,
    "Person": Person,
    "Team": Team,
    "Component": Component,
}

DEFAULT_EDGE_TYPES: Dict[str, Type[BaseModel]] = {
    "WorksOn": WorksOn,
    "Owns": Owns,
    "DependsOn": DependsOn,
    "Implements": Implements,
    "Blocks": Blocks,
    "Decides": Decides,
    "Mentions": Mentions,
    "HasFeature": HasFeature,
}

DEFAULT_EDGE_TYPE_MAP: Mapping[Tuple[str, str], Sequence[str]] = {
    ("Person", "Product"): ["WorksOn", "Mentions"],
    ("Person", "Feature"): ["WorksOn", "Mentions"],
    ("Person", "Decision"): ["Decides", "Mentions"],
    ("Team", "Product"): ["Owns", "WorksOn"],
    ("Team", "Feature"): ["WorksOn"],
    ("Product", "Feature"): ["HasFeature"],
    ("Feature", "Product"): ["Implements", "DependsOn"],
    ("Feature", "Feature"): ["DependsOn", "Blocks"],
    ("Issue", "Feature"): ["Blocks", "DependsOn"],
    ("Issue", "Product"): ["Blocks", "DependsOn"],
    ("Release", "Product"): ["Implements", "DependsOn"],
    ("Release", "Feature"): ["Implements", "DependsOn"],
    ("Decision", "Feature"): ["Decides"],
    ("Decision", "Product"): ["Decides"],
    ("Component", "Product"): ["DependsOn", "Owns", "Mentions"],
    ("Component", "Component"): ["DependsOn"],
    ("Entity", "Entity"): ["Mentions"],
}

DEFAULT_EXCLUDED_ENTITY_TYPES: Sequence[str] = []
