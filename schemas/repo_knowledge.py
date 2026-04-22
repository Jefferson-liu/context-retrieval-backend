from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RunStatus = Literal["queued", "in_progress", "completed", "failed", "skipped_duplicate"]
SourceType = Literal["local_path", "git_url"]
SubjectType = Literal["file", "class", "func", "external"]
ParseStatus = Literal[
    "pending",
    "success",
    "failed",
    "unsupported_language",
    "skipped_too_large",
]


class RepoRunCreateRequest(BaseModel):
    """Request payload for creating a repository ingestion run."""

    source_type: SourceType = Field(default="local_path")
    source_path: str = Field(..., min_length=1, description="Local path to a repository root.")
    repo_address: str | None = Field(default=None, description="Logical repository identifier.")
    include_extensions: list[str] | None = Field(default=None)
    exclude_globs: list[str] | None = Field(default=None)
    force_reingest: bool = Field(default=False)


class RepoRunCreateResponse(BaseModel):
    """Response returned after a run is queued."""

    run_id: str
    status: RunStatus
    queued_at: datetime


class RepoRunStatusResponse(BaseModel):
    """Detailed run status response."""

    run_id: str
    status: RunStatus
    source_type: SourceType
    repo_address: str
    source_locator: str
    fingerprint: str | None = None
    files_seen: int
    files_ingested: int
    files_skipped: int
    chunks_written: int
    parse_success_count: int
    parse_failed_count: int
    edge_count_file: int
    edge_count_symbol: int
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoLinkedFileSummaryRunResponse(BaseModel):
    """File-summary run metadata linked to a source repository run."""

    file_summary_run_id: str
    status: str
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoRunListItemResponse(BaseModel):
    """One source repository run item in the list response."""

    run_id: str
    status: RunStatus
    source_type: SourceType
    repo_address: str
    source_locator: str
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    file_summary_runs: list[RepoLinkedFileSummaryRunResponse] = Field(default_factory=list)


class RepoRunListResponse(BaseModel):
    """Paginated source repository runs with linked file_summary run ids."""

    items: list[RepoRunListItemResponse] = Field(default_factory=list)
    limit: int
    offset: int


class RepoFileSnapshotResponse(BaseModel):
    """Metadata for one file snapshot in a run."""

    run_id: str
    subject_id: str
    subject_path: str
    subject_type: SubjectType
    language: str | None = None
    size_bytes: int | None = None
    line_count: int | None = None
    content_hash: str | None = None
    ingest_status: str
    parse_status: ParseStatus
    skip_reason: str | None = None
    parse_error: str | None = None
    chunk_count: int


class RepoFileSnapshotListResponse(BaseModel):
    """Paginated file snapshot response."""

    items: list[RepoFileSnapshotResponse] = Field(default_factory=list)
    limit: int
    offset: int


class RepoEdgeResponse(BaseModel):
    """Serialized dependency edge."""

    run_id: str
    from_subject_id: str
    to_subject_id: str
    from_subject_type: SubjectType
    to_subject_type: SubjectType
    from_subject_path: str
    to_subject_path: str
    edge_type: str
    line: int | None = None
    column: int | None = None
    evidence: str | None = None
    is_external_target: bool


class RepoEdgeListResponse(BaseModel):
    """Paginated edge response."""

    items: list[RepoEdgeResponse] = Field(default_factory=list)
    limit: int
    offset: int
