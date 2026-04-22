from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field


class SummaryOutput(BaseModel):
    """Strict LLM output schema for repository file summaries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_cluster: list[str] = Field(default_factory=list)
    overall_summary: str = Field(..., min_length=1)
    important_relationships: list[str] = Field(default_factory=list)
    group_function: str | None = None


@dataclass(slots=True)
class SummaryNeighbor:
    """Graph-neighbor detail used to enrich summary prompts."""

    direction: str
    edge_type: str
    related_subject_path: str
    related_subject_type: str
    line: int | None = None
    column: int | None = None


@dataclass(slots=True)
class SummaryInput:
    """Assembled per-file context passed to the file summarizer."""

    source_run_id: str
    subject_id: str
    subject_path: str
    language: str | None
    parse_status: str
    repo_path: str | None = None
    repo_address: str | None = None
    tech_stack: str | None = None
    chunk_texts: list[str] = field(default_factory=list)
    neighbors: list[SummaryNeighbor] = field(default_factory=list)
