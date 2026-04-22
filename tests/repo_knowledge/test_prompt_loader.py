from __future__ import annotations

import pytest

from services.repo_knowledge.prompt_loader import load_prompt, render_prompt


def test_load_prompt_reads_prompt_file() -> None:
    prompt = load_prompt("file_summary_system")
    assert "code analysis assistant" in prompt


def test_render_prompt_formats_template_variables() -> None:
    prompt = render_prompt(
        "file_summary_user",
        prompt_version="v1",
        subject_path="a.py",
        language="python",
        parse_status="success",
        tech="python",
        repo_path="/tmp/repo",
        original_code_content="print('code chunk')",
    )
    assert "Subject path: a.py" in prompt
    assert "code chunk" in prompt


def test_render_prompt_raises_for_missing_variable() -> None:
    with pytest.raises(ValueError):
        render_prompt("file_summary_user", subject_path="a.py")


def test_load_repo_full_summary_prompt_files() -> None:
    system_prompt = load_prompt("repo_full_summary_system")
    user_prompt = render_prompt(
        "repo_full_summary_user",
        prompt_version="v1",
        tech="python",
        repo_path="/tmp/repo",
    )
    assert "business-logic" in system_prompt.lower() or "README" in system_prompt
    assert "Repository path: /tmp/repo" in user_prompt
