from pydantic import BaseModel, Field
from typing import List, Optional


class TextThreadMessageInput(BaseModel):
    type: str = Field(default="message", description="Message type")
    user: Optional[str] = Field(default=None, description="User identifier")
    text: str = Field(..., description="Message text content")


class UploadTextThreadRequest(BaseModel):
    title: str | None = Field(default=None, description="Optional thread title")
    source_system: str = Field(default="manual", description="Origin system name")
    external_thread_id: str | None = Field(default=None, description="Optional external thread id")
    messages: List[TextThreadMessageInput] = Field(
        default_factory=list,
        description="Optional list of messages to build the thread text",
    )
