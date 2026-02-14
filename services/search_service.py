from __future__ import annotations

from typing import Any, Optional

from graphiti_core import Graphiti  # type: ignore


class SearchService:
    """Thin wrapper around Graphiti search."""

    def __init__(self, *, graphiti_client: Graphiti, group_ids: list[str]) -> None:
        self.graphiti = graphiti_client
        self.group_ids = group_ids

    async def search(self, query: str) -> Any:
        results = await self.graphiti.search(
            query=query,
            group_ids=self.group_ids,
        )
        payload = []
        for item in results:
            payload.append(
                {
                    "fact": item.fact,
                    "valid_at": item.valid_at,
                    "invalid_at": item.invalid_at,
                }
            )
        return results
