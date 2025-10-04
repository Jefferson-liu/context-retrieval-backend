from __future__ import annotations

import sys
from typing import Dict

from pymilvus import connections, utility

from config import settings


def _connection_params() -> Dict[str, object]:
    params: Dict[str, object] = {
        "alias": "milvus-healthcheck",
        "host": settings.MILVUS_HOST,
        "port": str(settings.MILVUS_PORT),
    }
    if settings.MILVUS_USERNAME:
        params["user"] = settings.MILVUS_USERNAME
    if settings.MILVUS_PASSWORD:
        params["password"] = settings.MILVUS_PASSWORD
    return params


def main() -> int:
    params = _connection_params()
    alias = params["alias"]
    try:
        connections.connect(**params)
        has_collection = utility.has_collection(settings.MILVUS_COLLECTION_NAME, using=alias)
        status = "present" if has_collection else "missing"
        print(
            f"Milvus connection succeeded (host={settings.MILVUS_HOST}, port={settings.MILVUS_PORT}). "
            f"Collection '{settings.MILVUS_COLLECTION_NAME}' is {status}."
        )
        return 0
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"Milvus healthcheck failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            connections.disconnect(alias)
        except Exception:  # pragma: no cover - best effort cleanup
            pass


if __name__ == "__main__":
    sys.exit(main())
