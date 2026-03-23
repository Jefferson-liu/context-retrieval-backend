from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class RepoFullSummaryOutput(BaseModel):
    """Strict output schema for repository README full summaries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    readme_markdown: str = Field(..., min_length=1)


@dataclass(slots=True)
class RepoFullSummaryInput:
    """Assembled context passed to the repo full-summary agent."""

    source_run_id: str
    source_file_summary_run_id: str
    repo_path: str
    repo_address: str
    tech_stack: str
