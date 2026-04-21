from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


SourceType = Literal["local_path", "git_url"]
PipelineStatus = Literal["queued", "in_progress", "completed", "failed"]
PipelineStage = Literal[
    "queued",
    "ingestion",
    "file_summary",
    "repo_full_summary",
    "embedding",
    "repo_manager",
    "architecture",
    "completed",
    "failed",
]


class PipelineStageProgress(BaseModel):
    """Per-stage progress counts for the currently active pipeline stage."""

    items_total: int = 0
    items_completed: int = 0
    items_failed: int = 0


class RepoPipelineRunCreateRequest(BaseModel):
    """Request payload for starting a full repo-knowledge pipeline from a source path."""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType = Field(default="local_path")
    source_path: str = Field(..., min_length=1, description="Local path or git URL to a repository.")
    repo_address: str | None = Field(default=None, description="Logical repository identifier.")
    git_token: str | None = Field(default=None, description="Token for cloning private git repositories. Never stored.")
    resume_from_file_summary_run_id: str | None = Field(default=None, description="Skip ingestion and file summary — resume pipeline from this completed file_summary_run_id.")
    include_extensions: list[str] | None = Field(default=None)
    exclude_globs: list[str] | None = Field(default=None)
    force_reingest: bool = Field(default=False)
    force_refile_summary: bool = Field(default=False)
    force_rerepo_summary: bool = Field(default=False)
    force_reembed: bool = Field(default=False)
    force_rerepo_manager: bool = Field(
        default=False,
        validation_alias=AliasChoices("force_rerepo_manager", "force_resummarize"),
    )


class RepoPipelineRunCreateResponse(BaseModel):
    """Response returned after a pipeline run is accepted and queued."""

    run_id: str
    status: PipelineStatus
    stage: PipelineStage
    file_summary_run_id: str | None = None
    repo_full_summary_run_id: str | None = None
    embedding_run_id: str | None = None
    repo_manager_run_id: str | None = None
    queued_at: datetime


class RepoPipelineRunStatusResponse(BaseModel):
    """Detailed status for a pipeline run keyed by source ingestion run id."""

    run_id: str
    status: PipelineStatus
    stage: PipelineStage
    source_type: SourceType
    repo_address: str
    source_locator: str
    source_run_status: str
    file_summary_run_id: str | None = None
    file_summary_run_status: str | None = None
    repo_full_summary_run_id: str | None = None
    repo_full_summary_run_status: str | None = None
    embedding_run_id: str | None = None
    embedding_run_status: str | None = None
    repo_manager_run_id: str | None = None
    repo_manager_run_status: str | None = None
    error_message: str | None = None
    stage_error_message: str | None = None
    files_seen: int = 0
    files_ingested: int = 0
    stage_progress: PipelineStageProgress | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoPipelineRunListResponse(BaseModel):
    """Paginated list of pipeline runs with full stage status."""

    items: list[RepoPipelineRunStatusResponse] = Field(default_factory=list)
    limit: int
    offset: int
