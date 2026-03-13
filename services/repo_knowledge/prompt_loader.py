from __future__ import annotations

from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=128)
def load_prompt(prompt_name: str) -> str:
    """Load one prompt template from the repo-knowledge prompt directory."""

    path = PROMPTS_DIR / f"{prompt_name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file is empty: {path}")
    return text


def render_prompt(prompt_name: str, **values: str) -> str:
    """Render a named prompt template using Python format placeholders."""

    template = load_prompt(prompt_name)
    try:
        return template.format(**values)
    except KeyError as exc:
        raise ValueError(f"Missing prompt template variable '{exc.args[0]}' for {prompt_name}") from exc
