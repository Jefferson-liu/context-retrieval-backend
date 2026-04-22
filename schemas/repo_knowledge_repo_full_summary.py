from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RepoFullSummaryRunStatus = Literal["queued", "in_progress", "completed", "failed"]


class RepoFullSummaryRunCreateRequest(BaseModel):
    """Request payload for creating a repo full-summary (README) run."""

    model_config = ConfigDict(extra="forbid")

    source_file_summary_run_id: str = Field(..., min_length=1)
    force_rerepo_summary: bool = Field(default=False)


class RepoFullSummaryRunCreateResponse(BaseModel):
    """Response returned after a repo full-summary run is queued or reused."""

    repo_full_summary_run_id: str
    status: RepoFullSummaryRunStatus
    queued_at: datetime


class RepoFullSummaryRunStatusResponse(BaseModel):
    """Detailed repo full-summary run status response."""

    repo_full_summary_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    status: RepoFullSummaryRunStatus
    prompt_version: str
    files_seen: int
    files_used: int
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoFullSummaryReadmeResponse(BaseModel):
    """Canonical README artifact response for one repo full-summary run."""

    repo_full_summary_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    prompt_version: str
    finished_at: datetime | None = None
    readme_markdown: str
