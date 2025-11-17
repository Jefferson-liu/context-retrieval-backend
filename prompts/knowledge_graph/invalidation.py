from __future__ import annotations

from typing import List, Dict

from langchain_core.prompts import ChatPromptTemplate

from schemas.knowledge_graph.temporal_event import TemporalEvent


def format_events(primary_event: TemporalEvent, primary_triplet: str, secondary_event: TemporalEvent, secondary_triplet: str) -> str:
    lines = [
        f"Primary event: ",
        f"Statement: {primary_event.statement}",
        f"Triplet: {primary_triplet}",
        f"Valid at: {primary_event.valid_at}",
        f"Invalid at: {primary_event.invalid_at}",
        "---",
        f"Secondary event: ",
        f"Statement: {secondary_event.statement}",
        f"Triplet: {secondary_triplet}",
        f"Valid at: {secondary_event.valid_at}",
        f"Invalid at: {secondary_event.invalid_at}",
    ]
    return "\n".join(lines)


invalidation_prompt = ChatPromptTemplate.from_template(
    """
Task: Analyze the primary event against the secondary event and determine if the primary event is invalidated by the secondary event.
Only set dates if they explicitly relate to the validity of the relationship described in the text.

IMPORTANT: Only invalidate events if they are directly invalidated by the other event given in the context. Do NOT use any external knowledge to determine validity ranges.
Only use dates that are directly stated to invalidate the relationship. The invalid_at for the invalidated event should be the valid_at of the event that caused the invalidation.

Invalidation Guidelines:
1. Dates are given in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.SSSSSSZ).
2. Where invalid_at is null, it means this event is still valid and considered to be ongoing.
3. Where invalid_at is defined, the event has previously been invalidated by something else and can be considered "finished".
4. An event can refine the invalid_at of a finished event to an earlier date only.
5. An event cannot invalidate an event that chronologically occurred after it.
6. An event cannot be invalidated by an event that chronologically occurred before it.
7. An event cannot invalidate itself.

---
{events_block}
---

IF THE PRIMARY EVENT IS INVALIDATED OR YOU CHANGED ITS INVALID AT, RETURN "true". OTHERWISE, RETURN "false".
Do NOT return any explanations or additional text. ONLY return the boolean value.
"""
)


def build_invalidation_prompt(
    primary_statement: TemporalEvent,
    primary_triplet: str,
    secondary_statement: TemporalEvent,
    secondary_triplet: str,
):
    events_block = format_events(primary_statement, primary_triplet, secondary_statement, secondary_triplet)
    return invalidation_prompt.partial(
        events_block=events_block
    )


__all__ = [
    "build_invalidation_prompt",
]
