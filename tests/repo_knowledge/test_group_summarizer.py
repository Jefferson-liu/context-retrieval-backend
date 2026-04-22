from __future__ import annotations

import asyncio
from types import SimpleNamespace

from services.repo_knowledge.group_summarization.group_summarizer import RepoGroupSummarizer
from services.repo_knowledge.group_summarization.types import GroupMemberEvidence, GroupSummaryInput


class _FakeChatModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)

    async def ainvoke(self, _messages):  # noqa: ANN001
        if not self.responses:
            raise RuntimeError("No fake responses left")
        return SimpleNamespace(content=self.responses.pop(0))


def test_group_summarizer_parses_strict_json() -> None:
    summarizer = RepoGroupSummarizer(
        chat_model=_FakeChatModel(
            [
                '{"name":"Recommendation feature","overall_summary":"Combines ranking and delivery.",'
                '"business_purpose":"Delivers personalized content","responsibilities":["Rank candidates"],'
                '"tags":["recommendation"],"representative_subject_ids":["s1","unknown"],'
                '"is_infrastructure":false,"confidence":0.82}'
            ]
        ),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=8000,
        retry_count=1,
        timeout_seconds=5,
    )

    payload = GroupSummaryInput(
        source_run_id="run-1",
        source_file_summary_run_id="extract-1",
        group_id="group-1",
        group_key="services/recommendation",
        group_label="services/recommendation",
        layer_hint="service",
        is_infrastructure_seed=False,
        heuristics={"seed_parts": ["services/recommendation"]},
        dependency_neighbor_paths=["routers/recommendation/routes.py"],
        representative_subject_ids=["s1"],
        members=[
            GroupMemberEvidence(
                subject_id="s1",
                subject_path="services/recommendation/rank.py",
                language="python",
                overall_summary="Ranks recommendation candidates",
                group_function="Recommendation ranking",
                important_relationships=["calls scoring service"],
                is_representative=True,
                rank=1,
            )
        ],
    )
    result = asyncio.run(summarizer.summarize(payload=payload))

    assert result.output.name == "Recommendation feature"
    assert result.output.confidence == 0.82
    assert result.output.representative_subject_ids == ["s1"]


def test_group_summarizer_empty_group_fallback() -> None:
    summarizer = RepoGroupSummarizer(
        chat_model=_FakeChatModel([]),  # type: ignore[arg-type]
        prompt_version="v1",
        max_input_chars=8000,
        retry_count=1,
        timeout_seconds=5,
    )

    payload = GroupSummaryInput(
        source_run_id="run-1",
        source_file_summary_run_id="extract-1",
        group_id="group-1",
        group_key="services/empty",
        group_label="services/empty",
        layer_hint="service",
        is_infrastructure_seed=False,
        heuristics={},
        dependency_neighbor_paths=[],
        representative_subject_ids=[],
        members=[],
    )
    result = asyncio.run(summarizer.summarize(payload=payload))

    assert result.output.overall_summary == "Deterministic group has no members to summarize."
    assert result.raw_output["mode"] == "deterministic_empty"
