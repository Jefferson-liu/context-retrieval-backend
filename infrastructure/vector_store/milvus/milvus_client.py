from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from pymilvus import connections


class MilvusClientFactory:
    """Async-friendly helper that manages a single Milvus connection alias."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        secure: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._secure = secure
        self._alias = f"context-retrieval-{uuid.uuid4().hex}"
        self._connected = False
        self._lock = asyncio.Lock()

    async def ensure_connection(self) -> str:
        """Establish the connection if needed and return the alias."""

        if self._connected:
            return self._alias

        async with self._lock:
            if self._connected:
                return self._alias

            loop = asyncio.get_event_loop()

            def _connect() -> None:
                params = {
                    "alias": self._alias,
                    "host": self._host,
                    "port": str(self._port),
                }
                if self._username:
                    params["user"] = self._username
                if self._password:
                    params["password"] = self._password
                if self._secure:
                    params["secure"] = True

                connections.connect(**params)

            await loop.run_in_executor(None, _connect)
            self._connected = True

        return self._alias

    async def close(self) -> None:
        """Disconnect from Milvus if connected."""

        if not self._connected:
            return

        loop = asyncio.get_event_loop()

        def _disconnect() -> None:
            connections.disconnect(self._alias)

        await loop.run_in_executor(None, _disconnect)
        self._connected = False
