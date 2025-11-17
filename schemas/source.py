from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Source(BaseModel):
    doc_id: Optional[int]
    chunk_id: Optional[int]
    content: str
    doc_name: Optional[str]
