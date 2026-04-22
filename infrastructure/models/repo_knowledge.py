from __future__ import annotations

from datetime import datetime
import os

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - optional dependency in some environments
    Vector = None


def _repo_embed_vector_dim() -> int:
    raw = os.getenv("REPO_EMBED_VECTOR_DIM", "768").strip()
    try:
        value = int(raw)
        return value if value > 0 else 768
    except ValueError:
        return 768


REPO_EMBED_VECTOR_DIM = _repo_embed_vector_dim()


class RepoRunRecord(Base):
    """Represents one asynchronous repository ingestion run."""

    __tablename__ = "repo_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_locator: Mapped[str] = mapped_column(Text, nullable=False)
    repo_address: Mapped[str] = mapped_column(Text, nullable=False)
    include_extensions: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_globs: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunks_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count_file: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count_symbol: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_repo_runs_tenant_user_queued", "tenant_id", "user_id", "queued_at"),
        Index("ix_repo_runs_scope_fingerprint", "tenant_id", "user_id", "source_locator", "fingerprint"),
    )


class RepoSubjectRecord(Base):
    """Catalog of files and symbols found in analyzed repositories."""

    __tablename__ = "repo_subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repo_address: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    subject_path: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    symbol_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol_qualname: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    external_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "repo_address",
            "subject_path",
            "subject_type",
            "symbol_qualname",
            "external_ref",
            name="uq_repo_subjects_identity",
        ),
        Index("ix_repo_subjects_repo_type", "repo_address", "subject_type"),
    )


class RepoFileSnapshotRecord(Base):
    """Run-scoped metadata for each discovered file."""

    __tablename__ = "repo_file_snapshots"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("repo_runs.id", ondelete="CASCADE"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encoding: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ingest_status: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_repo_file_snapshots_run_ingest", "run_id", "ingest_status"),
    )


class RepoFileChunkRecord(Base):
    """Run-scoped text chunks for repository files."""

    __tablename__ = "repo_file_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("repo_runs.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "subject_id", "chunk_index", name="uq_repo_file_chunks_identity"),
        Index("ix_repo_file_chunks_run_subject", "run_id", "subject_id"),
    )


class RepoEdgeRecord(Base):
    """Run-scoped dependency edge between subjects."""

    __tablename__ = "repo_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("repo_runs.id", ondelete="CASCADE"), nullable=False)
    from_subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_external_target: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "from_subject_id",
            "to_subject_id",
            "edge_type",
            "line",
            "column",
            name="uq_repo_edges_identity",
        ),
        Index("ix_repo_edges_run_edge_type", "run_id", "edge_type"),
    )


class RepoParseDiagnosticRecord(Base):
    """Non-fatal parse diagnostics captured during ingestion."""

    __tablename__ = "repo_parse_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("repo_runs.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_repo_parse_diagnostics_run_subject", "run_id", "subject_id"),
    )


class RepoFileSummaryRunRecord(Base):
    """Represents one asynchronous repository summary file_summary run."""

    __tablename__ = "repo_file_summary_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    run_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_summarized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_repo_file_summary_runs_scope_status", "tenant_id", "user_id", "status"),
        Index(
            "ix_repo_file_summary_runs_idempotency",
            "source_run_id",
            "run_fingerprint",
            "status",
        ),
    )


class RepoFileSummaryRecord(Base):
    """LLM-generated summary artifact for one file subject in one file_summary run."""

    __tablename__ = "repo_file_summaries"

    file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_summary: Mapped[str] = mapped_column(Text, nullable=False)
    file_cluster: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    important_relationships: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    group_function: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_repo_file_summaries_source_run", "source_run_id"),
    )


class RepoFileSummaryDiagnosticRecord(Base):
    """Per-file non-fatal diagnostics produced by summary file_summary."""

    __tablename__ = "repo_file_summary_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_repo_file_summary_diagnostics_run_subject", "file_summary_run_id", "subject_id"),
    )


class RepoFileSummaryUsageRecord(Base):
    """Per-file token usage and agent trace for one file-summary invocation."""

    __tablename__ = "repo_file_summary_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    llm_step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_repo_file_summary_usage_run", "file_summary_run_id"),
        Index("ix_repo_file_summary_usage_subject", "subject_id"),
    )


class RepoFullSummaryRunRecord(Base):
    """Represents one asynchronous repo-level full-summary (README) run."""

    __tablename__ = "repo_full_summary_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    run_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_repo_full_summary_runs_scope_status", "tenant_id", "user_id", "status"),
        Index(
            "ix_repo_full_summary_runs_idempotency",
            "source_run_id",
            "source_file_summary_run_id",
            "run_fingerprint",
            "status",
        ),
    )


class RepoFullSummaryRecord(Base):
    """Persisted repo-level README markdown artifact for one full-summary run."""

    __tablename__ = "repo_full_summaries"

    repo_full_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_full_summary_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    readme_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_repo_full_summaries_source_run", "source_run_id"),
    )


class RepoFullSummaryDiagnosticRecord(Base):
    """Non-fatal diagnostics emitted while generating repo full summaries."""

    __tablename__ = "repo_full_summary_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repo_full_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_full_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_repo_full_summary_diagnostics_run", "repo_full_summary_run_id"),
    )


class RepoEmbeddingRunRecord(Base):
    """Represents one asynchronous repository embedding generation run."""

    __tablename__ = "repo_embedding_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    subjects_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subjects_embedded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subjects_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_repo_embedding_runs_scope_status", "tenant_id", "user_id", "status"),
        Index(
            "ix_repo_embedding_runs_idempotency",
            "source_run_id",
            "source_file_summary_run_id",
            "run_fingerprint",
            "status",
        ),
    )


class RepoEmbeddingRecord(Base):
    """Embedding vector stored for one summarized repository subject."""

    __tablename__ = "repo_embeddings"

    embedding_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_embedding_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text_for_embedding: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(REPO_EMBED_VECTOR_DIM) if Vector is not None else JSON,
        nullable=False,
    )
    embedding_dims: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    if Vector is not None:
        __table_args__ = (
            Index("ix_repo_embeddings_run_kind", "embedding_run_id", "kind"),
            Index(
                "ix_repo_embeddings_embedding_ivfflat",
                "embedding",
                postgresql_using="ivfflat",
                postgresql_with={"lists": 100},
                postgresql_ops={"embedding": "vector_cosine_ops"},
            ),
        )
    else:
        __table_args__ = (
            Index("ix_repo_embeddings_run_kind", "embedding_run_id", "kind"),
        )


class RepoEmbeddingDiagnosticRecord(Base):
    """Per-subject non-fatal diagnostics produced during embedding generation."""

    __tablename__ = "repo_embedding_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    embedding_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_embedding_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_repo_embedding_diagnostics_run_subject", "embedding_run_id", "subject_id"),
    )


class RepoManagerRunRecord(Base):
    """Represents one asynchronous repo-manager run derived from file summaries."""

    __tablename__ = "repo_manager_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)

    groups_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    groups_summarized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    groups_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    members_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    architecture_overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    merged_mermaid_diagram: Mapped[str | None] = mapped_column(Text, nullable=True)
    merge_raw_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_repo_manager_runs_scope_status", "tenant_id", "user_id", "status"),
        Index(
            "ix_repo_manager_runs_idempotency",
            "source_run_id",
            "source_file_summary_run_id",
            "run_fingerprint",
            "status",
        ),
    )


class RepoManagerSegmentRecord(Base):
    """One deterministic file segment produced during a repo-manager run."""

    __tablename__ = "repo_manager_segments"

    repo_manager_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_manager_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_key: Mapped[str] = mapped_column(Text, nullable=False)
    group_label: Mapped[str] = mapped_column(Text, nullable=False)
    layer_hint: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dependency_neighbor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_infrastructure_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    heuristics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("repo_manager_run_id", "group_key", name="uq_repo_manager_segments_run_group_key"),
        Index("ix_repo_manager_segments_run_layer", "repo_manager_run_id", "layer_hint"),
    )


class RepoManagerSegmentMemberRecord(Base):
    """Membership relation between a segment and its file subjects."""

    __tablename__ = "repo_manager_segment_members"

    repo_manager_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_manager_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_representative: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    membership_reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["repo_manager_run_id", "group_id"],
            ["repo_manager_segments.repo_manager_run_id", "repo_manager_segments.group_id"],
            ondelete="CASCADE",
            name="fk_repo_manager_segment_members_segment",
        ),
        UniqueConstraint(
            "repo_manager_run_id",
            "group_id",
            "subject_id",
            name="uq_repo_manager_segment_members_identity",
        ),
        Index("ix_repo_manager_segment_members_run_group_rank", "repo_manager_run_id", "group_id", "rank"),
    )


class RepoManagerSegmentSummaryRecord(Base):
    """LLM-generated architecture summary for one segment."""

    __tablename__ = "repo_manager_segment_summaries"

    repo_manager_run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_summary_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_file_summary_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    overall_summary: Mapped[str] = mapped_column(Text, nullable=False)
    business_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    responsibilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    representative_subject_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mermaid_diagram: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_infrastructure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    raw_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["repo_manager_run_id", "group_id"],
            ["repo_manager_segments.repo_manager_run_id", "repo_manager_segments.group_id"],
            ondelete="CASCADE",
            name="fk_repo_manager_segment_summaries_segment",
        ),
        Index("ix_repo_manager_segment_summaries_source_run", "source_run_id"),
    )


class RepoManagerDiagnosticRecord(Base):
    """Per-segment diagnostics emitted while generating architecture summaries."""

    __tablename__ = "repo_manager_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repo_manager_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repo_manager_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_repo_manager_diagnostics_run_group",
            "repo_manager_run_id",
            "group_id",
        ),
    )
