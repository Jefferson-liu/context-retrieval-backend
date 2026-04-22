from __future__ import annotations

from types import SimpleNamespace

from services.repo_knowledge.retrieval.context_pack_service import _build_repo_brief, _clamp_score


def test_clamp_score_bounds_values() -> None:
    assert _clamp_score(-1.0) == 0.0
    assert _clamp_score(0.5) == 0.5
    assert _clamp_score(3.0) == 1.0


def test_build_repo_brief_prefers_group_function() -> None:
    item = SimpleNamespace(
        candidate=SimpleNamespace(
            group_function="Processes billing state transitions",
            overall_summary="Billing service",
            subject_path="services/billing.py",
        )
    )
    brief = _build_repo_brief(items=[item])
    assert "Top business functions" in brief
    assert "Processes billing state transitions" in brief
