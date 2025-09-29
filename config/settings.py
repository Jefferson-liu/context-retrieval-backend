import os
from dotenv import load_dotenv

# Load environment variables from the project root (one level up from backend)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GIT_REPO_PATH = os.getenv("GIT_REPO_PATH")
REDIS_URL = os.getenv("REDIS_URL")

