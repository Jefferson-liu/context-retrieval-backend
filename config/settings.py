from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv


class Settings:
    """Application settings loaded from environment."""

    DATABASE_URL: str
    OPENAI_API_KEY: str | None
    GEMINI_API_KEY: str | None
    ANTHROPIC_API_KEY: str | None
    MODEL: str
    USE_PLACEHOLDER_SCOPE: bool
    DEFAULT_TENANT_ID: str
    DEFAULT_USER_ID: str
    APP_ENV: str
    REPO_INGEST_ALLOWED_ROOTS_LIST: list[str]
    REPO_INGEST_ALLOWED_EXTENSIONS_LIST: list[str]
    REPO_INGEST_EXCLUDED_DIRS_LIST: list[str]
    REPO_INGEST_MAX_FILE_BYTES: int
    REPO_INGEST_CHUNK_SIZE: int
    REPO_INGEST_CHUNK_OVERLAP: int
    REPO_INGEST_MAX_CONCURRENT_RUNS: int
    REPO_PARSE_MAX_FILE_BYTES: int
    REPO_PARSE_LANGUAGES_LIST: list[str]
    REPO_SUMMARY_MAX_CONCURRENT_RUNS: int
    REPO_SUMMARY_MAX_CONCURRENT_FILES: int
    REPO_SUMMARY_MAX_ITERATIONS: int
    REPO_SUMMARY_PROMPT_VERSION: str
    REPO_SUMMARY_MODEL_PROVIDER: str
    REPO_SUMMARY_MODEL_NAME: str
    REPO_SUMMARY_TEMPERATURE: float
    REPO_SUMMARY_MAX_INPUT_CHARS: int
    REPO_SUMMARY_MAP_CHUNK_CHARS: int
    REPO_SUMMARY_MAX_OUTPUT_TOKENS: int
    REPO_SUMMARY_RETRY_COUNT: int
    REPO_SUMMARY_TIMEOUT_SECONDS: int
    REPO_EMBED_MAX_CONCURRENT_RUNS: int
    REPO_EMBED_MODEL_PROVIDER: str
    REPO_EMBED_MODEL_NAME: str
    REPO_EMBED_VECTOR_DIM: int
    REPO_EMBED_BATCH_SIZE: int
    REPO_EMBED_TIMEOUT_SECONDS: int
    REPO_CONTEXT_TOP_K: int
    REPO_CONTEXT_CANDIDATE_K: int
    REPO_CONTEXT_NEIGHBOR_LIMIT_EACH_DIRECTION: int
    REPO_CONTEXT_SYMBOL_HINT_LIMIT: int
    REPO_CONTEXT_RERANK_MODEL_NAME: str
    REPO_CONTEXT_RERANK_TIMEOUT_SECONDS: int
    REPO_CONTEXT_RERANK_MAX_CANDIDATES: int
    REPO_MANAGER_MAX_CONCURRENT_RUNS: int
    REPO_MANAGER_PROMPT_VERSION: str
    REPO_MANAGER_TIMEOUT_SECONDS: int
    REPO_MANAGER_RETRY_COUNT: int
    REPO_MANAGER_MAX_INPUT_CHARS: int
    REPO_MANAGER_MAX_OUTPUT_TOKENS: int
    REPO_GROUP_SUMMARY_MAX_CONCURRENT_RUNS: int
    REPO_GROUP_SUMMARY_PROMPT_VERSION: str
    REPO_GROUP_SUMMARY_TIMEOUT_SECONDS: int
    REPO_GROUP_SUMMARY_RETRY_COUNT: int
    REPO_GROUP_SUMMARY_MAX_INPUT_CHARS: int
    REPO_GROUP_SUMMARY_MAX_OUTPUT_TOKENS: int
    REPO_ARCHITECTURE_MERGE_PROMPT_VERSION: str
    REPO_ARCHITECTURE_MERGE_TIMEOUT_SECONDS: int
    REPO_ARCHITECTURE_MERGE_RETRY_COUNT: int
    REPO_ARCHITECTURE_MERGE_MAX_INPUT_CHARS: int
    REPO_FULL_SUMMARY_MAX_CONCURRENT_RUNS: int
    REPO_FULL_SUMMARY_PROMPT_VERSION: str
    REPO_FULL_SUMMARY_TIMEOUT_SECONDS: int
    REPO_FULL_SUMMARY_RETRY_COUNT: int
    REPO_FULL_SUMMARY_MAX_INPUT_CHARS: int
    REPO_FULL_SUMMARY_MAX_ITERATIONS: int
    REPO_GROUP_PATH_DEPTH: int
    REPO_GROUP_DEP_MERGE_MIN_AFFINITY: float
    REPO_GROUP_MAX_MEMBER_FILES: int
    REPO_GROUP_REPRESENTATIVE_COUNT: int
    REPO_MANAGER_MAX_GROUP_TOKENS: int
    REPO_PIPELINE_MAX_CONCURRENT_RUNS: int
    REPO_PIPELINE_POLL_SECONDS: int

    def __init__(self) -> None:
        load_dotenv()
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL is not set. Please configure it in the environment or .env file.")
        self.OPENAI_API_KEY = os.getenv("PERSONAL_OPENAI_KEY")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.MODEL = os.getenv("MODEL", "openai").lower()
        self.APP_ENV = os.getenv("APP_ENV", "dev").lower()
        self.USE_PLACEHOLDER_SCOPE = (
            os.getenv("USE_PLACEHOLDER_SCOPE", "1" if self.APP_ENV in {"dev", "development"} else "0")
            .lower()
            not in {"0", "false", "no"}
        )
        self.DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "demo_tenant")
        self.DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "demo_user")
        self.SEMAPHORE_LIMIT = int(os.getenv("SEMAPHORE_LIMIT", "10"))
        default_root = os.getcwd()
        self.REPO_INGEST_ALLOWED_ROOTS_LIST = _parse_csv_env(
            os.getenv("REPO_INGEST_ALLOWED_ROOTS", default_root)
        )
        self.REPO_INGEST_ALLOWED_EXTENSIONS_LIST = _parse_csv_env(
            os.getenv(
                "REPO_INGEST_ALLOWED_EXTENSIONS",
                ".py,.ts,.tsx,.js,.jsx,.md,.txt,.yaml,.yml,.json,.toml,.ini,.cfg,.env",
            )
        )
        self.REPO_INGEST_EXCLUDED_DIRS_LIST = _parse_csv_env(
            os.getenv(
                "REPO_INGEST_EXCLUDED_DIRS",
                ".git,.venv,venv,node_modules,dist,build,__pycache__",
            )
        )
        self.REPO_INGEST_MAX_FILE_BYTES = int(os.getenv("REPO_INGEST_MAX_FILE_BYTES", "1048576"))
        self.REPO_INGEST_CHUNK_SIZE = int(os.getenv("REPO_INGEST_CHUNK_SIZE", "1000"))
        self.REPO_INGEST_CHUNK_OVERLAP = int(os.getenv("REPO_INGEST_CHUNK_OVERLAP", "120"))
        self.REPO_INGEST_MAX_CONCURRENT_RUNS = int(os.getenv("REPO_INGEST_MAX_CONCURRENT_RUNS", "2"))
        self.REPO_PARSE_MAX_FILE_BYTES = int(os.getenv("REPO_PARSE_MAX_FILE_BYTES", "524288"))
        self.REPO_PARSE_LANGUAGES_LIST = _parse_csv_env(
            os.getenv("REPO_PARSE_LANGUAGES", "python,typescript,javascript")
        )
        self.REPO_SUMMARY_MAX_CONCURRENT_RUNS = int(os.getenv("REPO_SUMMARY_MAX_CONCURRENT_RUNS", "1"))
        self.REPO_SUMMARY_MAX_CONCURRENT_FILES = int(os.getenv("REPO_SUMMARY_MAX_CONCURRENT_FILES", "8"))
        self.REPO_SUMMARY_MAX_ITERATIONS = int(os.getenv("REPO_SUMMARY_MAX_ITERATIONS", "6"))
        self.REPO_SUMMARY_PROMPT_VERSION = os.getenv("REPO_SUMMARY_PROMPT_VERSION", "v1")
        self.REPO_SUMMARY_MODEL_PROVIDER = os.getenv("REPO_SUMMARY_MODEL_PROVIDER", "gemini").lower()
        self.REPO_SUMMARY_MODEL_NAME = os.getenv(
            "REPO_SUMMARY_MODEL_NAME",
            _default_summary_model_name(self.REPO_SUMMARY_MODEL_PROVIDER),
        )
        self.REPO_SUMMARY_TEMPERATURE = float(os.getenv("REPO_SUMMARY_TEMPERATURE", "0.1"))
        self.REPO_SUMMARY_MAX_INPUT_CHARS = int(os.getenv("REPO_SUMMARY_MAX_INPUT_CHARS", "24000"))
        self.REPO_SUMMARY_MAP_CHUNK_CHARS = int(os.getenv("REPO_SUMMARY_MAP_CHUNK_CHARS", "6000"))
        self.REPO_SUMMARY_MAX_OUTPUT_TOKENS = int(os.getenv("REPO_SUMMARY_MAX_OUTPUT_TOKENS", "900"))
        self.REPO_SUMMARY_RETRY_COUNT = int(os.getenv("REPO_SUMMARY_RETRY_COUNT", "2"))
        self.REPO_SUMMARY_TIMEOUT_SECONDS = int(os.getenv("REPO_SUMMARY_TIMEOUT_SECONDS", "60"))
        self.REPO_EMBED_MAX_CONCURRENT_RUNS = int(os.getenv("REPO_EMBED_MAX_CONCURRENT_RUNS", "1"))
        self.REPO_EMBED_MODEL_PROVIDER = os.getenv("REPO_EMBED_MODEL_PROVIDER", "gemini").lower()
        self.REPO_EMBED_MODEL_NAME = os.getenv("REPO_EMBED_MODEL_NAME", "gemini-embedding-001")
        self.REPO_EMBED_VECTOR_DIM = int(os.getenv("REPO_EMBED_VECTOR_DIM", "768"))
        self.REPO_EMBED_BATCH_SIZE = int(os.getenv("REPO_EMBED_BATCH_SIZE", "32"))
        self.REPO_EMBED_TIMEOUT_SECONDS = int(os.getenv("REPO_EMBED_TIMEOUT_SECONDS", "60"))
        self.REPO_CONTEXT_TOP_K = int(os.getenv("REPO_CONTEXT_TOP_K", "12"))
        self.REPO_CONTEXT_CANDIDATE_K = int(os.getenv("REPO_CONTEXT_CANDIDATE_K", "40"))
        self.REPO_CONTEXT_NEIGHBOR_LIMIT_EACH_DIRECTION = int(
            os.getenv("REPO_CONTEXT_NEIGHBOR_LIMIT_EACH_DIRECTION", "6")
        )
        self.REPO_CONTEXT_SYMBOL_HINT_LIMIT = int(os.getenv("REPO_CONTEXT_SYMBOL_HINT_LIMIT", "8"))
        self.REPO_CONTEXT_RERANK_MODEL_NAME = os.getenv("REPO_CONTEXT_RERANK_MODEL_NAME", "gemini-2.5-flash")
        self.REPO_CONTEXT_RERANK_TIMEOUT_SECONDS = int(os.getenv("REPO_CONTEXT_RERANK_TIMEOUT_SECONDS", "45"))
        self.REPO_CONTEXT_RERANK_MAX_CANDIDATES = int(os.getenv("REPO_CONTEXT_RERANK_MAX_CANDIDATES", "40"))
        self.REPO_MANAGER_MAX_CONCURRENT_RUNS = int(
            os.getenv(
                "REPO_MANAGER_MAX_CONCURRENT_RUNS",
                os.getenv("REPO_GROUP_SUMMARY_MAX_CONCURRENT_RUNS", "1"),
            )
        )
        self.REPO_MANAGER_PROMPT_VERSION = os.getenv(
            "REPO_MANAGER_PROMPT_VERSION",
            os.getenv("REPO_GROUP_SUMMARY_PROMPT_VERSION", "v1"),
        )
        self.REPO_MANAGER_TIMEOUT_SECONDS = int(
            os.getenv(
                "REPO_MANAGER_TIMEOUT_SECONDS",
                os.getenv("REPO_GROUP_SUMMARY_TIMEOUT_SECONDS", "60"),
            )
        )
        self.REPO_MANAGER_RETRY_COUNT = int(
            os.getenv(
                "REPO_MANAGER_RETRY_COUNT",
                os.getenv("REPO_GROUP_SUMMARY_RETRY_COUNT", "2"),
            )
        )
        self.REPO_MANAGER_MAX_INPUT_CHARS = int(
            os.getenv(
                "REPO_MANAGER_MAX_INPUT_CHARS",
                os.getenv("REPO_GROUP_SUMMARY_MAX_INPUT_CHARS", "26000"),
            )
        )
        self.REPO_MANAGER_MAX_OUTPUT_TOKENS = int(
            os.getenv(
                "REPO_MANAGER_MAX_OUTPUT_TOKENS",
                os.getenv("REPO_GROUP_SUMMARY_MAX_OUTPUT_TOKENS", "1800"),
            )
        )
        self.REPO_GROUP_SUMMARY_MAX_CONCURRENT_RUNS = self.REPO_MANAGER_MAX_CONCURRENT_RUNS
        self.REPO_GROUP_SUMMARY_PROMPT_VERSION = self.REPO_MANAGER_PROMPT_VERSION
        self.REPO_GROUP_SUMMARY_TIMEOUT_SECONDS = self.REPO_MANAGER_TIMEOUT_SECONDS
        self.REPO_GROUP_SUMMARY_RETRY_COUNT = self.REPO_MANAGER_RETRY_COUNT
        self.REPO_GROUP_SUMMARY_MAX_INPUT_CHARS = self.REPO_MANAGER_MAX_INPUT_CHARS
        self.REPO_GROUP_SUMMARY_MAX_OUTPUT_TOKENS = self.REPO_MANAGER_MAX_OUTPUT_TOKENS
        self.REPO_ARCHITECTURE_MERGE_PROMPT_VERSION = os.getenv("REPO_ARCHITECTURE_MERGE_PROMPT_VERSION", "v1")
        self.REPO_ARCHITECTURE_MERGE_TIMEOUT_SECONDS = int(os.getenv("REPO_ARCHITECTURE_MERGE_TIMEOUT_SECONDS", "180"))
        self.REPO_ARCHITECTURE_MERGE_RETRY_COUNT = int(os.getenv("REPO_ARCHITECTURE_MERGE_RETRY_COUNT", "2"))
        self.REPO_ARCHITECTURE_MERGE_MAX_INPUT_CHARS = int(os.getenv("REPO_ARCHITECTURE_MERGE_MAX_INPUT_CHARS", "32000"))
        self.REPO_FULL_SUMMARY_MAX_CONCURRENT_RUNS = int(os.getenv("REPO_FULL_SUMMARY_MAX_CONCURRENT_RUNS", "1"))
        self.REPO_FULL_SUMMARY_PROMPT_VERSION = os.getenv("REPO_FULL_SUMMARY_PROMPT_VERSION", "v1")
        self.REPO_FULL_SUMMARY_TIMEOUT_SECONDS = int(os.getenv("REPO_FULL_SUMMARY_TIMEOUT_SECONDS", "300"))
        self.REPO_FULL_SUMMARY_RETRY_COUNT = int(os.getenv("REPO_FULL_SUMMARY_RETRY_COUNT", "2"))
        self.REPO_FULL_SUMMARY_MAX_INPUT_CHARS = int(os.getenv("REPO_FULL_SUMMARY_MAX_INPUT_CHARS", "30000"))
        self.REPO_FULL_SUMMARY_MAX_ITERATIONS = int(os.getenv("REPO_FULL_SUMMARY_MAX_ITERATIONS", "25"))
        self.REPO_GROUP_PATH_DEPTH = int(os.getenv("REPO_GROUP_PATH_DEPTH", "2"))
        self.REPO_GROUP_DEP_MERGE_MIN_AFFINITY = float(os.getenv("REPO_GROUP_DEP_MERGE_MIN_AFFINITY", "0.35"))
        self.REPO_GROUP_MAX_MEMBER_FILES = int(os.getenv("REPO_GROUP_MAX_MEMBER_FILES", "60"))
        self.REPO_GROUP_REPRESENTATIVE_COUNT = int(os.getenv("REPO_GROUP_REPRESENTATIVE_COUNT", "8"))
        self.REPO_MANAGER_MAX_GROUP_TOKENS = int(os.getenv("REPO_MANAGER_MAX_GROUP_TOKENS", "5000"))
        self.REPO_PIPELINE_MAX_CONCURRENT_RUNS = int(os.getenv("REPO_PIPELINE_MAX_CONCURRENT_RUNS", "2"))
        self.REPO_PIPELINE_POLL_SECONDS = int(os.getenv("REPO_PIPELINE_POLL_SECONDS", "2"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _parse_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_summary_model_name(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "gemini":
        return "gemini-2.5-flash"
    if normalized == "anthropic":
        return "claude-3-5-haiku-latest"
    return "gpt-4o-mini"
