from __future__ import annotations

from services.repo_knowledge.ingestion_service import (
    MAX_EXTERNAL_REF_CHARS,
    _compact_external_reference,
    _select_external_reference,
)
from services.repo_knowledge.parsing.types import ParsedEdge


def _build_edge(
    *,
    edge_type: str,
    to_symbol_ref: str | None,
    to_file_or_external: str | None,
) -> ParsedEdge:
    return ParsedEdge(
        edge_type=edge_type,
        from_symbol_ref=None,
        to_symbol_ref=to_symbol_ref,
        from_file="src/app.ts",
        to_file_or_external=to_file_or_external,
        line=1,
        column=1,
        evidence=None,
    )


def test_select_external_reference_prefers_symbol_for_calls() -> None:
    edge = _build_edge(
        edge_type="calls",
        to_symbol_ref="safeName",
        to_file_or_external="very.long.raw.call.expression()",
    )
    assert _select_external_reference(edge=edge) == "safeName"


def test_select_external_reference_prefers_import_target_for_imports() -> None:
    edge = _build_edge(
        edge_type="imports",
        to_symbol_ref="helper",
        to_file_or_external="./utils/helper",
    )
    assert _select_external_reference(edge=edge) == "./utils/helper"


def test_compact_external_reference_hashes_oversized_value() -> None:
    raw = "a" * (MAX_EXTERNAL_REF_CHARS + 1)
    compact, hashed = _compact_external_reference(raw)
    assert hashed is True
    assert compact.startswith("ext_sha256:")


def test_compact_external_reference_keeps_small_value() -> None:
    raw = "module.symbol"
    compact, hashed = _compact_external_reference(raw)
    assert hashed is False
    assert compact == raw
