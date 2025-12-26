from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DataCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Title of the data record")
    body: str = Field(..., min_length=1, description="Body/content to be chunked and stored")


class ChunkResponse(BaseModel):
    id: int
    index: int
    content: str


class DataListItem(BaseModel):
    id: int
    title: str
    body: str


class DataResponse(BaseModel):
    id: int
    title: str
    body: str
    chunk_count: Optional[int] = None
    chunks: Optional[List[ChunkResponse]] = None
