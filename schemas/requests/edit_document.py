from pydantic import BaseModel, Field


class EditDocumentRequest(BaseModel):
    content: str = Field(..., min_length=1)
    doc_type: str | None = None
    commit_message: str | None = None
