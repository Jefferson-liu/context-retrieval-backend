from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GroupSummaryRunStatus = Literal["queued", "in_progress", "completed", "failed"]


class RepoGroupSummaryRunCreateRequest(BaseModel):
    """Request payload for creating a group-summary run."""

    model_config = ConfigDict(extra="forbid")

    source_file_summary_run_id: str = Field(..., min_length=1)
    force_resummarize: bool = Field(default=False)


class RepoGroupSummaryRunCreateResponse(BaseModel):
    """Response returned after a group-summary run is queued or reused."""

    group_summary_run_id: str
    status: GroupSummaryRunStatus
    queued_at: datetime


class RepoGroupSummaryRunStatusResponse(BaseModel):
    """Detailed group-summary run status response."""

    group_summary_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    status: GroupSummaryRunStatus
    prompt_version: str
    groups_seen: int
    groups_summarized: int
    groups_failed: int
    members_seen: int
    architecture_overview: str | None = None
    merged_mermaid_diagram_available: bool = False
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoGroupSummaryMemberResponse(BaseModel):
    """One group member file in a group summary payload."""

    subject_id: str
    subject_path: str
    language: str | None = None
    rank: int
    is_representative: bool
    membership_reason: str


class RepoGroupSummaryItemResponse(BaseModel):
    """Serialized group summary item with deterministic grouping metadata."""

    group_id: str
    group_key: str
    group_label: str
    layer_hint: str
    member_count: int
    dependency_neighbor_count: int
    is_infrastructure_seed: bool
    heuristics: dict
    name: str | None = None
    overall_summary: str | None = None
    business_purpose: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    representative_subject_ids: list[str] = Field(default_factory=list)
    mermaid_diagram: str | None = None
    is_infrastructure: bool | None = None
    confidence: float | None = None
    updated_at: datetime | None = None
    members: list[RepoGroupSummaryMemberResponse] = Field(default_factory=list)


class RepoGroupSummaryArchitectureResponse(BaseModel):
    """Merged repo-level architecture artifact for one repo-manager run."""

    group_summary_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    prompt_version: str
    architecture_overview: str
    mermaid_diagram: str
    finished_at: datetime | None = None


class RepoGroupSummaryItemListResponse(BaseModel):
    """Paginated list of group summary items for one group-summary run."""

    items: list[RepoGroupSummaryItemResponse] = Field(default_factory=list)
    limit: int
    offset: int
    include_members: bool


class RepoLatestGroupSummaryResponse(BaseModel):
    """Latest completed group-summary payload for a source run."""

    group_summary_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    prompt_version: str
    finished_at: datetime | None = None
    include_members: bool
    items: list[RepoGroupSummaryItemResponse] = Field(default_factory=list)
