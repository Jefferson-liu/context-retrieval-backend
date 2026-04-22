from __future__ import annotations

from infrastructure.models import RepoFileSnapshotRecord, RepoSubjectRecord
from infrastructure.repositories import RepoChunkRepository
from services.repo_knowledge.summarization.types import SummaryInput


class SummaryContextAssembler:
    """Build summary input payloads from chunks and metadata."""

    def __init__(
        self,
        *,
        chunk_repo: RepoChunkRepository,
    ) -> None:
        self.chunk_repo = chunk_repo

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
        )
