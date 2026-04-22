from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from infrastructure.models import RepoFileSnapshotRecord, RepoSubjectRecord, RepoFileSummaryRecord

FILE_SUMMARY_KIND = "file_summary"


@dataclass(slots=True)
class EmbeddingTextPayload:
    """Deterministic text payload used for repository summary embeddings."""

    kind: str
    text_for_embedding: str
    text_hash: str


def build_file_summary_embedding_text(
    *,
    summary: RepoFileSummaryRecord,
    subject: RepoSubjectRecord,
    snapshot: RepoFileSnapshotRecord | None,
) -> EmbeddingTextPayload:
    """Build normalized embedding text for one file summary artifact."""
    lines: list[str] = [
        f"subject_path: {subject.subject_path}",
        f"language: {subject.language or 'unknown'}",
        f"parse_status: {snapshot.parse_status if snapshot else 'unknown'}",
        f"overall_summary: {summary.overall_summary}",
    ]
    if summary.group_function:
        lines.append(f"group_function: {summary.group_function}")

    if summary.file_cluster:
        lines.append("file_cluster:")
        for item in summary.file_cluster:
            lines.append(f"- {item}")

    if summary.important_relationships:
        lines.append("important_relationships:")
        for item in summary.important_relationships:
            lines.append(f"- {item}")

    text = "\n".join(lines).strip()
    digest = sha256(text.encode("utf-8")).hexdigest()
    return EmbeddingTextPayload(
        kind=FILE_SUMMARY_KIND,
        text_for_embedding=text,
        text_hash=digest,
    )
