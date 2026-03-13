from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EmbeddingRunStatus = Literal["queued", "in_progress", "completed", "failed"]


class RepoEmbeddingRunCreateRequest(BaseModel):
    """Request payload for creating a repository embedding run."""

    model_config = ConfigDict(extra="forbid")

    source_file_summary_run_id: str | None = Field(default=None, min_length=1)
    source_run_id: str | None = Field(default=None, min_length=1)
    repo_run_id: str | None = Field(default=None, min_length=1)
    force_reembed: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_run_selectors(self) -> "RepoEmbeddingRunCreateRequest":
        """Require file_summary or source run selector and normalize repo_run_id."""

        if self.source_run_id and self.repo_run_id and self.source_run_id != self.repo_run_id:
            raise ValueError("source_run_id and repo_run_id must match when both are provided")

        resolved_source_run_id = self.source_run_id or self.repo_run_id
        if not self.source_file_summary_run_id and not resolved_source_run_id:
            raise ValueError(
                "Provide source_file_summary_run_id or one of source_run_id/repo_run_id"
            )

        self.source_run_id = resolved_source_run_id
        return self


class RepoEmbeddingRunCreateResponse(BaseModel):
    """Response returned after an embedding run is queued or reused."""

    embedding_run_id: str
    status: EmbeddingRunStatus
    queued_at: datetime


class RepoEmbeddingRunStatusResponse(BaseModel):
    """Detailed embedding run status response."""

    embedding_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    status: EmbeddingRunStatus
    subjects_seen: int
    subjects_embedded: int
    subjects_failed: int
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RepoEmbeddingItemResponse(BaseModel):
    """Serialized metadata for one stored repo embedding record."""

    embedding_run_id: str
    source_run_id: str
    source_file_summary_run_id: str
    subject_id: str
    subject_path: str
    language: str | None = None
    kind: str
    text_hash: str
    embedding_dims: int
    updated_at: datetime


class RepoEmbeddingItemListResponse(BaseModel):
    """Paginated list of embedding metadata rows."""

    items: list[RepoEmbeddingItemResponse] = Field(default_factory=list)
    limit: int
    offset: int


class RepoContextPackRequest(BaseModel):
    """Request payload to build a retrieval context pack for one run and query."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=12, ge=1, le=100)
    candidate_k: int = Field(default=40, ge=1, le=200)
    neighbor_limit_each_direction: int = Field(default=6, ge=1, le=50)


class RepoContextNeighborResponse(BaseModel):
    """One file-level neighbor edge included in context-pack output."""

    direction: Literal["incoming", "outgoing"]
    edge_type: str
    related_subject_path: str
    related_subject_type: str
    line: int | None = None
    column: int | None = None


class RepoContextSymbolHintResponse(BaseModel):
    """Symbol-level hint attached to a context-pack file item."""

    symbol_name: str
    symbol_qualname: str
    relationships: list[str] = Field(default_factory=list)


class RepoContextPackItemResponse(BaseModel):
    """One ranked context item containing summary plus graph/symbol hints."""

    subject_id: str
    subject_path: str
    language: str | None = None
    parse_status: str | None = None
    overall_summary: str
    file_cluster: list[str]
    important_relationships: list[str]
    group_function: str | None = None
    similarity_score: float
    rerank_score: float
    final_score: float
    rerank_reason: str | None = None
    neighbors: list[RepoContextNeighborResponse] = Field(default_factory=list)
    symbol_hints: list[RepoContextSymbolHintResponse] = Field(default_factory=list)


class RepoContextPackResponse(BaseModel):
    """Context-pack response composed from summary embeddings and dependency graph expansion."""

    source_run_id: str
    embedding_run_id: str
    file_summary_run_id: str
    query: str
    repo_brief: str
    rerank_applied: bool
    items: list[RepoContextPackItemResponse] = Field(default_factory=list)
