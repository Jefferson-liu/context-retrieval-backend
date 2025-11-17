from pydantic import BaseModel, Field


class RawTemporalRange(BaseModel):
    """Model representing the raw temporal validity range as strings."""

    valid_at: str | None = Field(..., json_schema_extra={"format": "date-time"})
    invalid_at: str | None = Field(..., json_schema_extra={"format": "date-time"})


class RawTemporalRangeList(BaseModel):
    """Structured container for one or more temporal ranges."""

    ranges: list[RawTemporalRange]
