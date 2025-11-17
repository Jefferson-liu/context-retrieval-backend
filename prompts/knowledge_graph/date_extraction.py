from __future__ import annotations

from typing import Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from .definitions import LABEL_DEFINITIONS
from schemas.knowledge_graph.raw_statement import RawStatement
from schemas.knowledge_graph.enums.types import StatementType, TemporalType


_GUIDANCE_KEYS = (
    ("definition", "Definition"),
    ("date_handling_guidance", "Guidance"),
    ("date_handling_example", "Example"),
)


def tidy(name: str) -> str:
    """Replace underscores with spaces."""
    return name.replace("_", " ")


def render_inputs(inputs: RawStatement, reference_dates: str | None = None) -> str:
    """Combine the inputs and optional reference timestamp into bullet lines."""
    if not inputs:
        return ""
    lines = [
        f"statement: {inputs.statement}",
        f"- statement type: {inputs.statement_type.value}",
        f"- temporal type: {inputs.temporal_type.value}",
    ]
    if reference_dates:
        lines.append(f"- reference timestamp: {reference_dates}")
    return "\n".join(lines)


def render_guidance(details: Optional[Dict[str, str]]) -> str:
    if not details:
        return ""
    lines = []
    for key, label in _GUIDANCE_KEYS:
        value = details.get(key)
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _statement_guidance(statement_type: StatementType) -> str:
    return render_guidance(
        LABEL_DEFINITIONS["episode_labelling"].get(statement_type.value)
    )


def _temporal_guidance(temporal_type: TemporalType) -> str:
    return render_guidance(
        LABEL_DEFINITIONS["temporal_labelling"].get(temporal_type.value)
    )


date_extraction_prompt = ChatPromptTemplate.from_template(
    """
You are a temporal reasoning assistant.

TASK:
- Analyze the statement and determine the temporal validity range as dates for the temporal event or relationship described.
- Use only the explicit temporal information in the text, the guidance below, and the reference timestamp if provided. Do not use external knowledge.
- Only set dates if they directly relate to when the relationship held true. If the statement reflects a single-point event with a known date, set only `valid_at`.

Validity Range Definitions:
- `valid_at` is when the relationship became true or was observed.
- `invalid_at` is when that relationship ended (can be null if still ongoing).

General Guidelines:
  1. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SS.SSSSSSZ) for datetimes.
  2. Use the reference or publication date as the current time when determining the valid_at and invalid_at dates.
  3. If the fact is written in the present tense without containing temporal information, use the reference or publication date for the valid_at date
  4. Do not infer dates from related events or external knowledge. Only use dates that are directly stated to establish or change the relationship.
  5. Convert relative times (e.g., “two weeks ago”) into absolute ISO 8601 datetimes based on the reference or publication timestamp.
  6. If only a date is mentioned without a specific time, use 00:00:00 (midnight) for that date.
  7. If only year or month is mentioned, use the start or end as appropriate at 00:00:00 e.g. do not select a random date if only the year is mentioned, use YYYY-01-01 or YYYY-12-31.
  8. Always include the time zone offset (use Z for UTC if no specific time zone is mentioned).

Statement Specific Rules:
- when `statement_type` is **opinion** only valid_at must be set
- when `statement_type` is **prediction** set its `invalid_at` to the **end of the prediction window** explicitly mentioned in the text.

Never invent dates from outside knowledge.


INPUTS:
{rendered_inputs}

{temporal_type_upper} Temporal Type Specific Guidance:
{rendered_temporal_guidance}

{statement_type_upper} Statement Type Specific Guidance:
{rendered_statement_guidance}

"""
)

def build_date_extraction_prompt(
    statement: RawStatement,
    reference_dates: str | None = None,
) -> ChatPromptTemplate:
    """Prepare the date extraction prompt using guidance from LABEL_DEFINITIONS. The input will be a RawStatement."""
    return date_extraction_prompt.partial(
        rendered_inputs=render_inputs(
            statement, reference_dates=reference_dates),
        temporal_type_upper=statement.temporal_type.value.upper(),
        rendered_temporal_guidance=_temporal_guidance(statement.temporal_type),
        statement_type_upper=statement.statement_type.value.upper(),
        rendered_statement_guidance=_statement_guidance(
            statement.statement_type),
    )
__all__ = [
    "build_date_extraction_prompt",
]
