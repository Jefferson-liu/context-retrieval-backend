from pydantic import BaseModel


class InvalidationDecision(BaseModel):
    """Represents a single invalidation recommendation."""

    statement_id: str
    reason: str | None = None


class InvalidationDecisionList(BaseModel):
    """Structured output for invalidation agent responses."""

    invalidate: list[InvalidationDecision]
