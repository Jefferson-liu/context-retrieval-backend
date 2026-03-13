from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GroupFileNode:
    """File-level summary node used as input to deterministic grouping."""

    subject_id: str
    subject_path: str
    language: str | None
    overall_summary: str
    group_function: str | None
    important_relationships: list[str]


@dataclass(slots=True)
class GroupFileEdge:
    """File-to-file edge used to compute inter-group affinity and representative rank."""

    from_subject_id: str
    to_subject_id: str
    edge_type: str


@dataclass(slots=True)
class GroupMember:
    """One file member assigned to a deterministic group."""

    subject_id: str
    rank: int
    is_representative: bool
    membership_reason: str


@dataclass(slots=True)
class BuiltGroup:
    """Deterministic group emitted by the grouping strategy before LLM summarization."""

    group_id: str
    group_key: str
    group_label: str
    layer_hint: str
    member_count: int
    dependency_neighbor_count: int
    is_infrastructure_seed: bool
    heuristics: dict
    representative_subject_ids: list[str]
    members: list[GroupMember] = field(default_factory=list)


@dataclass(slots=True)
class GroupBuildResult:
    """Grouping result payload for one source file_summary run."""

    groups: list[BuiltGroup]
    members_seen: int
