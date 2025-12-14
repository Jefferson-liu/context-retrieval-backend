from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment."""

    DATABASE_URL: str

    def __init__(self) -> None:
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
