from __future__ import annotations

import logging
import re
import os
from functools import lru_cache
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

from graphiti_core import Graphiti


@lru_cache(maxsize=1)
def get_graphiti_client() -> Optional[Graphiti]:
    """Return a cached Graphiti client if configuration and dependency are present."""
    settings = get_settings()
    if Graphiti is None:
        logger.warning("graphiti-core not installed; Graphiti features disabled.")
        return None
    if not (settings.NEO4J_URI and settings.NEO4J_USER and settings.NEO4J_PASSWORD):
        logger.warning("Graphiti configuration missing; set NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD.")
        return None
    if settings.OPENAI_API_KEY:
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    else:
        logger.warning("OPENAI_API_KEY is not set; Graphiti LLM-backed ingestion may fail.")
    return Graphiti(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
    )


async def ensure_bootstrap() -> None:
    """Run index/constraint bootstrap once if supported."""
    client = get_graphiti_client()
    if client and hasattr(client, "build_indices_and_constraints"):
        try:
            await client.build_indices_and_constraints()
        except Exception as exc:  # pragma: no cover - bootstrap errors
            logger.warning("Graphiti bootstrap failed: %s", exc)


def build_group_id(tenant_id: str, user_id: str) -> str:
    """Sanitize and construct a Graphiti group_id."""
    raw = f"{tenant_id}_{user_id}"
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", raw)
    logger.info(f"Built group_id: {safe}")
    return safe
