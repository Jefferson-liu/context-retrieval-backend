from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExtractionRunStatus = Literal["queued", "in_progress", "completed", "failed"]


class RepoFileSummaryRunCreateRequest(BaseModel):
    """Request payload for creating a summary file_summary run."""

    model_config = ConfigDict(extra="forbid")

    source_run_id: str | None = Field(default=None, min_length=1)
    repo_run_id: str | None = Field(default=None, min_length=1)
    force_refile_summary: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_run_selector(self) -> "RepoFileSummaryRunCreateRequest":
        """Require one source run selector and normalize repo_run_id into source_run_id."""

        if self.source_run_id and self.repo_run_id and self.source_run_id != self.repo_run_id:
            raise ValueError("source_run_id and repo_run_id must match when both are provided")

        resolved_source_run_id = self.source_run_id or self.repo_run_id
        if not resolved_source_run_id:
            raise ValueError("Provide one of source_run_id or repo_run_id")

        self.source_run_id = resolved_source_run_id
        return self


class RepoFileSummaryRunCreateResponse(BaseModel):
    """Response returned after a summary file_summary run is queued or reused."""

    file_summary_run_id: str
    status: ExtractionRunStatus
    queued_at: datetime


class RepoFileSummaryRunStatusResponse(BaseModel):
    """Detailed file_summary run status response."""

    file_summary_run_id: str
    source_run_id: str
    status: ExtractionRunStatus
    prompt_version: str
    files_seen: int
    files_summarized: int
    files_failed: int
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoFileSummaryResponse(BaseModel):
    """Serialized summary artifact for a file subject."""

    file_summary_run_id: str
    source_run_id: str
    subject_id: str
    subject_path: str
    language: str | None = None
    parse_status: str | None = None
    overall_summary: str
    file_cluster: list[str]
    important_relationships: list[str]
    group_function: str | None = None
    updated_at: datetime


class RepoFileSummaryListResponse(BaseModel):
    """Paginated list of summary artifacts."""

    items: list[RepoFileSummaryResponse] = Field(default_factory=list)
    limit: int
    offset: int


class RepoFileSummaryDiagnosticResponse(BaseModel):
    """Serialized diagnostic for one failed file-summary attempt."""

    file_summary_run_id: str
    source_run_id: str
    subject_id: str
    subject_path: str
    severity: str
    message: str
    details: dict | None = None
    created_at: datetime


class RepoFileSummaryDiagnosticListResponse(BaseModel):
    """Paginated list of file-summary diagnostics."""

    items: list[RepoFileSummaryDiagnosticResponse] = Field(default_factory=list)
    limit: int
    offset: int


class RepoLatestFileSummaryResponse(BaseModel):
    """Latest completed file_summary summaries for a source ingestion run."""

    file_summary_run_id: str
    source_run_id: str
    prompt_version: str
    finished_at: datetime | None = None
    items: list[RepoFileSummaryResponse] = Field(default_factory=list)


class RepoFileSummaryUsageItem(BaseModel):
    """Per-file token usage and agent trace for one summarization attempt."""

    file_summary_run_id: str
    subject_id: str
    subject_path: str
    model_provider: str
    model_name: str
    status: str
    error_message: str | None = None
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    llm_step_count: int
    tool_call_count: int
    duration_ms: int | None = None
    steps: list[dict] = Field(default_factory=list)
    created_at: datetime


class RepoFileSummaryUsageListResponse(BaseModel):
    """Paginated list of per-file usage records."""

    items: list[RepoFileSummaryUsageItem] = Field(default_factory=list)
    limit: int
    offset: int


class RepoFileSummaryUsageSummaryResponse(BaseModel):
    """Aggregated token usage summary for an entire file-summary run."""

    file_summary_run_id: str
    file_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    avg_duration_ms: float | None = None
    avg_tokens_per_file: float | None = None
