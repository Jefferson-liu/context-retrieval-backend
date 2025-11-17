from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from config import settings


@dataclass(slots=True)
class ExternalUser:
    """Lightweight representation of a user returned by the upstream directory."""

    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


class UserDirectoryClient:
    """Client for the upstream service that owns user data."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = settings.USER_DIRECTORY_BASE_URL,
        api_key: Optional[str] = settings.USER_DIRECTORY_API_KEY,
        timeout: float = 10.0,
    ) -> None:
        if base_url:
            base_url = base_url.rstrip("/")
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout

    async def fetch_user(self, external_id: str) -> ExternalUser | None:
        """Fetch a user record from the upstream directory."""
        if settings.IS_DEV_MODE and external_id == settings.DEV_PLACEHOLDER_USER_ID:
            return ExternalUser(
                user_id=settings.DEV_PLACEHOLDER_USER_ID,
                name=settings.DEV_PLACEHOLDER_USER_NAME,
                raw={"mode": "dev"},
            )

        if not self._base_url:
            raise RuntimeError("USER_DIRECTORY_BASE_URL is not configured")

        url = f"{self._base_url}/users/{external_id}"
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        payload = response.json()

        return ExternalUser(
            user_id=payload.get("id") or external_id,
            name=payload.get("name"),
            email=payload.get("email"),
            raw=payload,
        )
