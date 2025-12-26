from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv


class Settings:
    """Application settings loaded from environment."""

    DATABASE_URL: str
    NEO4J_URI: str | None
    NEO4J_USER: str | None
    NEO4J_PASSWORD: str | None
    OPENAI_API_KEY: str | None
    USE_PLACEHOLDER_SCOPE: bool
    DEFAULT_TENANT_ID: str
    DEFAULT_USER_ID: str
    APP_ENV: str

    def __init__(self) -> None:
        load_dotenv()
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set. Please configure it in the environment or .env file.")
        self.NEO4J_URI = os.getenv("NEO4J_URI")
        self.NEO4J_USER = os.getenv("NEO4J_USER")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
        self.OPENAI_API_KEY = os.getenv("PRODUCT_OS_OPENAI_KEY")
        self.APP_ENV = os.getenv("APP_ENV", "dev").lower()
        self.USE_PLACEHOLDER_SCOPE = (
            os.getenv("USE_PLACEHOLDER_SCOPE", "1" if self.APP_ENV in {"dev", "development"} else "0")
            .lower()
            not in {"0", "false", "no"}
        )
        # Defaults are underscore/dash safe for Graphiti group_ids.
        self.DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "demo_tenant")
        self.DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "demo_user")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
