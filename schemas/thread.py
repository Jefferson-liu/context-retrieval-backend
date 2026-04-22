from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ThreadCreateRequest(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., description="Slack-like messages payload")


class ThreadIngestResponse(BaseModel):
    id: int
    title: str
    body: str
    chunk_count: Optional[int] = None
    graph_entities: Optional[List[Dict[str, Any]]] = None
    graph_edges: Optional[List[Dict[str, Any]]] = None
    invalidated_edges: Optional[List[Dict[str, Any]]] = None
