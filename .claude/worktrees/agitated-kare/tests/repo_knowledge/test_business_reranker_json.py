from __future__ import annotations

import pytest

from services.repo_knowledge.retrieval.business_reranker import BusinessLogicRerankerError, _extract_json


def test_extract_json_accepts_markdown_fence() -> None:
    payload = _extract_json('```json\n{"items":[{"subject_id":"a","score":0.9,"reason":"core flow"}]}\n```')
    assert "items" in payload
    assert payload["items"][0]["subject_id"] == "a"


def test_extract_json_rejects_invalid_payload() -> None:
    with pytest.raises(BusinessLogicRerankerError):
        _extract_json("not-json")
