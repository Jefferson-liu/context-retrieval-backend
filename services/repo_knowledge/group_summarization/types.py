from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class GroupSummaryOutput(BaseModel):
    """Strict JSON schema expected from the architecture segment prompt."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    overall_summary: str = Field(..., min_length=1)
    business_purpose: str = Field(..., min_length=1)
    responsibilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    representative_subject_ids: list[str] = Field(default_factory=list)
    mermaid_diagram: str = Field(..., min_length=1)
    is_infrastructure: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


@dataclass(slots=True)
class GroupMemberEvidence:
    """One summarized file payload included in group-level summarization context."""

    subject_id: str
    subject_path: str
    language: str | None
    overall_summary: str
    group_function: str | None
    important_relationships: list[str]
    is_representative: bool
    rank: int


@dataclass(slots=True)
class GroupSummaryInput:
    """Prompt material for summarizing one deterministic group."""

    source_run_id: str
    source_file_summary_run_id: str
    group_id: str
    group_key: str
    group_label: str
    layer_hint: str
    is_infrastructure_seed: bool
    heuristics: dict
    dependency_neighbor_paths: list[str]
    representative_subject_ids: list[str]
    members: list[GroupMemberEvidence]
