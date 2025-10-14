from pydantic import BaseModel, Field, model_validator


class EditChunkRequest(BaseModel):
    content: str | None = None
    
    @model_validator(mode="after")
    def validate_payload(cls, values: "EditChunkRequest") -> "EditChunkRequest":
        if values.content is None:
            raise ValueError("'content' must be provided")
        if values.content is not None:
            stripped = values.content.strip()
            if not stripped:
                raise ValueError("'content' cannot be empty when provided")
            values.content = stripped
        return values
