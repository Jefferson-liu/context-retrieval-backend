from __future__ import annotations

from types import SimpleNamespace

from services.repo_knowledge.embeddings.text_builder import (
    FILE_SUMMARY_KIND,
    build_file_summary_embedding_text,
)


def test_build_file_summary_embedding_text_is_deterministic() -> None:
    summary = SimpleNamespace(
        overall_summary="Handles checkout workflow",
        group_function="Checkout and payment orchestration",
        file_cluster=["services/payment.py"],
        important_relationships=["calls PaymentGateway"],
    )
    subject = SimpleNamespace(
        subject_path="services/checkout.py",
        language="python",
    )
    snapshot = SimpleNamespace(parse_status="success")

    first = build_file_summary_embedding_text(
        summary=summary,  # type: ignore[arg-type]
        subject=subject,  # type: ignore[arg-type]
        snapshot=snapshot,  # type: ignore[arg-type]
    )
    second = build_file_summary_embedding_text(
        summary=summary,  # type: ignore[arg-type]
        subject=subject,  # type: ignore[arg-type]
        snapshot=snapshot,  # type: ignore[arg-type]
    )

    assert first.kind == FILE_SUMMARY_KIND
    assert first.text_for_embedding == second.text_for_embedding
    assert first.text_hash == second.text_hash
    assert "overall_summary: Handles checkout workflow" in first.text_for_embedding
    assert "group_function: Checkout and payment orchestration" in first.text_for_embedding
