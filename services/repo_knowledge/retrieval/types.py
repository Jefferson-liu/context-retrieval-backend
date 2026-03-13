from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ContextCandidate:
    """Candidate summary row before reranking and graph expansion."""

    subject_id: str
    subject_path: str
    language: str | None
    parse_status: str | None
    overall_summary: str
    file_cluster: list[str]
    important_relationships: list[str]
    group_function: str | None
    similarity_score: float


@dataclass(slots=True)
class RerankResult:
    """Rerank output for one candidate subject."""

    subject_id: str
    rerank_score: float
    reason: str | None = None


@dataclass(slots=True)
class ContextPackItem:
    """Final context-pack ranked item with optional graph and symbol hints."""

    candidate: ContextCandidate
    rerank_score: float
    final_score: float
    rerank_reason: str | None
    neighbors: list[dict] = field(default_factory=list)
    symbol_hints: list[dict] = field(default_factory=list)
