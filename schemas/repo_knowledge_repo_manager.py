from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


RepoManagerRunStatus = Literal["queued", "in_progress", "completed", "failed"]


class RepoManagerRunCreateRequest(BaseModel):
    """Request payload for creating a repo-manager architecture run."""

    model_config = ConfigDict(extra="forbid")

    source_file_summary_run_id: str = Field(..., min_length=1)
    force_rerepo_manager: bool = Field(
        default=False,
        validation_alias=AliasChoices("force_rerepo_manager", "force_resummarize"),
    )


class RepoManagerRunCreateResponse(BaseModel):
    """Response returned after a repo-manager run is queued or reused."""

    repo_manager_run_id: str
    status: RepoManagerRunStatus
    queued_at: datetime


class RepoManagerRunStatusResponse(BaseModel):
    """Detailed repo-manager run status response."""

    repo_manager_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    status: RepoManagerRunStatus
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


class RepoManagerSegmentMemberResponse(BaseModel):
    """One file/member in a repo-manager segment response."""

    subject_id: str
    subject_path: str
    language: str | None = None
    rank: int
    is_representative: bool
    membership_reason: str


class RepoManagerSegmentResponse(BaseModel):
    """Serialized repo-manager segment with architecture metadata."""

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
    members: list[RepoManagerSegmentMemberResponse] = Field(default_factory=list)


class RepoArchitectureResponse(BaseModel):
    """Merged repo-level architecture artifact for one repo-manager run."""

    repo_manager_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    prompt_version: str
    architecture_overview: str
    mermaid_diagram: str
    finished_at: datetime | None = None


class RepoManagerSegmentListResponse(BaseModel):
    """Paginated list of repo-manager segments for one run."""

    items: list[RepoManagerSegmentResponse] = Field(default_factory=list)
    limit: int
    offset: int
    include_members: bool


class RepoLatestRepoManagerResponse(BaseModel):
    """Latest completed repo-manager payload for a source run."""

    repo_manager_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    prompt_version: str
    finished_at: datetime | None = None
    include_members: bool
    items: list[RepoManagerSegmentResponse] = Field(default_factory=list)