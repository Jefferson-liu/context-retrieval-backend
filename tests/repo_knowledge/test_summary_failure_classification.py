from __future__ import annotations

from services.repo_knowledge.file_summary_service import _classify_file_summary_failure
from services.repo_knowledge.repo_full_summary_service import _classify_repo_full_summary_failure
from services.repo_knowledge.summarization.react_agent_runtime import AgentProtocolError


def test_file_summary_failure_classification_protocol() -> None:
    code, message = _classify_file_summary_failure(
        AgentProtocolError(code="thought_signature_missing", message="missing thought_signature")
    )
    assert code == "thought_signature_missing"
    assert message == "summary_file_summary_agent_protocol_failed"


def test_file_summary_failure_classification_generic() -> None:
    code, message = _classify_file_summary_failure(RuntimeError("boom"))
    assert code == "summary_failed"
    assert message == "summary_file_summary_failed"


def test_repo_full_summary_failure_classification_protocol() -> None:
    code, message = _classify_repo_full_summary_failure(
        AgentProtocolError(code="thought_signature_missing", message="missing thought_signature")
    )
    assert code == "thought_signature_missing"
    assert message == "repo_full_summary_agent_protocol_failed"


def test_repo_full_summary_failure_classification_generic() -> None:
    code, message = _classify_repo_full_summary_failure(RuntimeError("boom"))
    assert code == "repo_full_summary_failed"
    assert message == "repo_full_summary_failed"
