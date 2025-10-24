import os
from dotenv import load_dotenv

# Load environment variables from the project root (one level up from backend)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    pg_host = os.getenv("PGHOST")
    pg_port = os.getenv("PGPORT", "5432")
    pg_db = os.getenv("PGDATABASE")
    pg_user = os.getenv("PGUSER")
    pg_password = os.getenv("PGPASSWORD")

    if all([pg_host, pg_db, pg_user, pg_password]):
        DATABASE_URL = (
            f"postgresql+asyncpg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        )

if DATABASE_URL is None:
    raise ValueError(
        "DATABASE_URL is not configured. Set DATABASE_URL explicitly or provide "
        "PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD environment variables."
    )

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GIT_REPO_PATH = os.getenv("GIT_REPO_PATH")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN")

# Embedding/vector configuration
EMBEDDING_VECTOR_DIM = int(os.getenv("EMBEDDING_VECTOR_DIM", "768"))

# Vector store backend configuration
VECTOR_STORE_MODE = os.getenv("VECTOR_STORE_MODE", "pgvector").lower()
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
MILVUS_USERNAME = os.getenv("MILVUS_USERNAME")
MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD")
MILVUS_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "document_chunks")
MILVUS_VECTOR_DIM = int(os.getenv("MILVUS_VECTOR_DIM", str(EMBEDDING_VECTOR_DIM)))
MILVUS_CONSISTENCY_LEVEL = os.getenv("MILVUS_CONSISTENCY_LEVEL", "Bounded")
