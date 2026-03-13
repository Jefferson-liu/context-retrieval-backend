from __future__ import annotations

from infrastructure.models import RepoFileSnapshotRecord, RepoSubjectRecord
from infrastructure.repositories import RepoChunkRepository, RepoEdgeRepository
from services.repo_knowledge.summarization.types import SummaryInput, SummaryNeighbor


class SummaryContextAssembler:
    """Build summary input payloads from chunks, metadata, and dependency neighbors."""

    def __init__(
        self,
        *,
        chunk_repo: RepoChunkRepository,
        edge_repo: RepoEdgeRepository,
        neighbor_limit_each_direction: int,
    ) -> None:
        self.chunk_repo = chunk_repo
        self.edge_repo = edge_repo
        self.neighbor_limit_each_direction = neighbor_limit_each_direction

    async def build(
        self,
        *,
        source_run_id: str,
        snapshot: RepoFileSnapshotRecord,
        subject: RepoSubjectRecord,
        repo_path: str | None = None,
        repo_address: str | None = None,
        tech_stack: str | None = None,
    ) -> SummaryInput:
        chunk_rows = await self.chunk_repo.list_for_subject(run_id=source_run_id, subject_id=subject.id)
        neighbor_rows = await self.edge_repo.list_neighbors_for_file(
            run_id=source_run_id,
            subject_id=subject.id,
            limit_each_direction=self.neighbor_limit_each_direction,
        )

        return SummaryInput(
            source_run_id=source_run_id,
            subject_id=subject.id,
            subject_path=subject.subject_path,
            language=subject.language,
            parse_status=snapshot.parse_status,
            repo_path=repo_path,
            repo_address=repo_address,
            tech_stack=tech_stack,
            chunk_texts=[row.content for row in chunk_rows],
            neighbors=[
                SummaryNeighbor(
                    direction=item["direction"],
                    edge_type=item["edge_type"],
                    related_subject_path=item["related_subject_path"],
                    related_subject_type=item["related_subject_type"],
                    line=item.get("line"),
                    column=item.get("column"),
                )
                for item in neighbor_rows
            ],
        )
