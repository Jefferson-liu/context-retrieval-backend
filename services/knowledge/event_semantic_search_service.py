from __future__ import annotations

from typing import List, Awaitable, Callable
from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.database.repositories.knowledge_event_repository import KnowledgeEventRepository


class EventSemanticSearchService:
    """Isolated helper to run statement-embedding semantic search for events."""

    def __init__(self, sessionmaker: async_sessionmaker, context) -> None:
        self._sessionmaker = sessionmaker
        self._context = context

    async def search(self, query_embedding: list[float], top_k: int = 5) -> list:
        async with self._sessionmaker() as session:
            repo = KnowledgeEventRepository(session, self._context)
            return await repo.semantic_search(query_embedding, top_k=top_k)

