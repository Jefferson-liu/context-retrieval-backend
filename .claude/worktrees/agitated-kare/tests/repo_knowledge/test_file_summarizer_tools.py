from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from services.repo_knowledge.summarization.file_summarizer import FileSummaryAgentTools
from services.repo_knowledge.summarization.types import SummaryInput


@dataclass
class _Subject:
    id: str
    subject_path: str
    subject_type: str
    symbol_name: str | None = None
    symbol_qualname: str | None = None


class _FakeSubjectRepo:
    def __init__(self) -> None:
        self._files: dict[str, _Subject] = {
            "src/a.py": _Subject(id="file-1", subject_path="src/a.py", subject_type="file"),
        }
        self._symbols_by_qual: dict[str, _Subject] = {
            "Service.run": _Subject(
                id="func-1",
                subject_path="src/a.py",
                subject_type="func",
                symbol_name="run",
                symbol_qualname="Service.run",
            )
        }
        self._symbols_by_name: dict[str, _Subject] = {
            "run": self._symbols_by_qual["Service.run"],
        }

    async def find_file_by_path(self, *, repo_address: str, subject_path: str):  # noqa: ANN001
        assert repo_address == "repo-address"
        return self._files.get(subject_path)

    async def find_symbol_by_qualname(self, *, repo_address: str, symbol_qualname: str):  # noqa: ANN001
        assert repo_address == "repo-address"
        return self._symbols_by_qual.get(symbol_qualname)

    async def find_symbol_by_name(self, *, repo_address: str, symbol_name: str):  # noqa: ANN001
        assert repo_address == "repo-address"
        return self._symbols_by_name.get(symbol_name)


class _FakeEdgeRepo:
    async def list_neighbors_for_subject(  # noqa: ANN001
        self,
        *,
        run_id: str,
        subject_id: str,
        limit_each_direction: int,
    ):
        assert run_id == "run-1"
        assert limit_each_direction == 25
        if subject_id == "file-1":
            return [
                {
                    "direction": "outgoing",
                    "edge_type": "imports",
                    "line": 1,
                    "column": 1,
                    "related_subject_path": "src/b.py",
                    "related_subject_type": "file",
                    "related_symbol_name": None,
                    "related_symbol_qualname": None,
                },
                {
                    "direction": "incoming",
                    "edge_type": "references",
                    "line": 10,
                    "column": 2,
                    "related_subject_path": "src/c.py",
                    "related_subject_type": "file",
                    "related_symbol_name": None,
                    "related_symbol_qualname": None,
                },
            ]
        return []


def _make_tools(tmp_path: Path) -> FileSummaryAgentTools:
    payload = SummaryInput(
        source_run_id="run-1",
        subject_id="file-1",
        subject_path="src/a.py",
        language="python",
        parse_status="success",
        repo_path=str(tmp_path),
        repo_address="repo-address",
        tech_stack="python",
        chunk_texts=["print('hello')"],
        neighbors=[],
    )
    return FileSummaryAgentTools(
        payload=payload,
        subject_repo=_FakeSubjectRepo(),  # type: ignore[arg-type]
        edge_repo=_FakeEdgeRepo(),  # type: ignore[arg-type]
        trace_sink=[],
    )


def test_return_directory_pagination(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("line1\nline2\n", encoding="utf-8")
    (tmp_path / "src" / "nested").mkdir()
    (tmp_path / "src" / "nested" / "b.py").write_text("b\n", encoding="utf-8")

    tools = _make_tools(tmp_path)
    result = asyncio.run(tools.return_directory(repo_path="src", depth=1, cursor=0, page_size=1))
    assert result["repo_path"] == "src"
    assert len(result["entries"]) == 1
    assert result["has_more"] is True


def test_return_directory_blocks_path_escape(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(tools.return_directory(repo_path="../", depth=1))


def test_return_file_code_paging(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("line1\nline2\nline3\n", encoding="utf-8")

    tools = _make_tools(tmp_path)
    first_page = asyncio.run(tools.return_file_code(use_path="a.py", start_line=1, max_lines=2))
    assert first_page["resolved_path"] == "src/a.py"
    assert first_page["start_line"] == 1
    assert first_page["end_line"] == 2
    assert first_page["has_more"] is True
    assert first_page["next_start_line"] == 3


def test_return_file_code_blocks_path_escape(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(tools.return_file_code(use_path="../secret.py"))


def test_return_reference_graph_for_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")

    tools = _make_tools(tmp_path)
    result = asyncio.run(
        tools.return_reference_graph(
            type="file",
            input_subject="src/a.py",
            limit_each_direction=25,
        )
    )
    assert result["resolved_subject"]["id"] == "file-1"
    assert len(result["incoming"]) == 1
    assert len(result["outgoing"]) == 1


def test_return_reference_graph_for_func(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path)
    result = asyncio.run(
        tools.return_reference_graph(
            type="func",
            input_subject="Service.run",
            limit_each_direction=25,
        )
    )
    assert result["resolved_subject"]["id"] == "func-1"


def test_return_reference_graph_unresolved_subject(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path)
    result = asyncio.run(
        tools.return_reference_graph(
            type="class",
            input_subject="UnknownClass",
            limit_each_direction=25,
        )
    )
    assert result["resolved_subject"] is None
