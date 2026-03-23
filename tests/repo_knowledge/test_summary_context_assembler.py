from __future__ import annotations

import asyncio
from dataclasses import dataclass

from services.repo_knowledge.summarization.context_assembler import SummaryContextAssembler


@dataclass
class _Chunk:
    content: str


@dataclass
class _Snapshot:
    parse_status: str


@dataclass
class _Subject:
    id: str
    subject_path: str
    language: str | None


class _FakeChunkRepo:
    async def list_for_subject(self, *, run_id: str, subject_id: str):  # noqa: ANN001
        assert run_id == "run-1"
        assert subject_id == "subject-1"
        return [_Chunk("a"), _Chunk("b")]


def test_summary_context_assembler_builds_chunks() -> None:
    assembler = SummaryContextAssembler(
        chunk_repo=_FakeChunkRepo(),  # type: ignore[arg-type]
    )
    result = asyncio.run(
        assembler.build(
            source_run_id="run-1",
            snapshot=_Snapshot(parse_status="success"),  # type: ignore[arg-type]
            subject=_Subject(id="subject-1", subject_path="a.py", language="python"),  # type: ignore[arg-type]
        )
    )
    assert result.subject_path == "a.py"
    assert result.chunk_texts == ["a", "b"]
