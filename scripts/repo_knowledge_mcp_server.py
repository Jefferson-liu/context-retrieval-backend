from __future__ import annotations

import os
from pathlib import Path
import sys

# `mcp run scripts/foo.py` loads with scripts/ as import base.
# Ensure repo root is importable for config/infrastructure/services modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.repo_knowledge.agent_mcp_app import mcp


def main() -> None:
    transport = os.getenv("REPO_KNOWLEDGE_MCP_TRANSPORT", "sse").strip().lower()
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("REPO_KNOWLEDGE_MCP_TRANSPORT must be one of: stdio,sse,streamable-http")
    mcp.run(transport=transport, host="0.0.0.0")  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
