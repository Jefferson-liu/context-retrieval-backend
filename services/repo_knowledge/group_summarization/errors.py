from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TraceableLLMError(Exception):
    """Structured LLM failure carrying stage metadata and raw model output."""

    stage: str
    diagnostic_code: str
    message: str
    raw_text: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message