from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.repositories import DataRepository, ChunkRepository
from services.chunking import chunk_thread

logger = logging.getLogger(__name__)


class ThreadService:
    """Service to ingest Slack-like threads and store chunks."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data_repo = DataRepository(session)
        self.chunk_repo = ChunkRepository(session)

    async def ingest_thread(self, *, messages: List[Dict[str, Any]]) -> dict:
        normalized_messages, canonical_thread_ts, earliest_ts, channel = _normalize_thread_messages(messages)
        sorted_messages = sorted(normalized_messages, key=_sort_key_by_ts)
        title = _build_thread_title(canonical_thread_ts, channel)
        thread_payload = {
            "thread_ts": canonical_thread_ts,
            "channel": channel,
            "messages": sorted_messages,
        }
        body = json.dumps(thread_payload, ensure_ascii=False)
        chunks = chunk_thread(
            sorted_messages,
            thread_ts=canonical_thread_ts,
            channel=channel,
        )
        record = await self.data_repo.create_with_chunks(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            title=title,
            body=body,
            chunks=[c["text"] for c in chunks],
        )

        await self.session.flush()
        return {
            "id": record.id,
            "title": record.title,
            "body": record.body,
            "chunk_count": len(chunks),
            "graph_entities": None,
            "graph_edges": None,
            "invalidated_edges": None,
        }


def _coerce_ts(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_slack_ts(value: Any) -> datetime | None:
    ts = _coerce_ts(value)
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _ts_sort_key(value: Any) -> float | None:
    parsed = _parse_slack_ts(value)
    if parsed:
        return parsed.timestamp()
    return None


def _sort_key_by_ts(msg: Dict[str, Any]) -> float:
    candidates = [
        _ts_sort_key(msg.get("ts")),
        _ts_sort_key(msg.get("thread_ts")),
    ]
    for candidate in candidates:
        if candidate is not None:
            return candidate
    return float("inf")


def _normalize_thread_messages(
    messages: Sequence[Dict[str, Any]]
) -> tuple[list[dict], str | None, datetime | None, str | None]:
    normalized: list[dict] = []
    canonical_thread_ts: str | None = None
    earliest_ts: datetime | None = None
    channel: str | None = None

    for msg in messages:
        text = str(msg.get("text") or "").strip()
        user_display = msg.get("user_display_name") or msg.get("user_name") or msg.get("username")
        user_id = msg.get("user_id") or msg.get("user")
        user_label = user_display or user_id or "unknown"
        ts = _coerce_ts(msg.get("ts") or msg.get("timestamp"))
        thread_ts = _coerce_ts(msg.get("thread_ts")) or ts or canonical_thread_ts
        if canonical_thread_ts is None and thread_ts:
            canonical_thread_ts = thread_ts
        channel_value = msg.get("channel") or msg.get("channel_id")
        if channel_value and channel is None:
            channel = channel_value
        for candidate in (ts, thread_ts):
            parsed = _parse_slack_ts(candidate)
            if parsed and (earliest_ts is None or parsed < earliest_ts):
                earliest_ts = parsed
        normalized.append(
            {
                "ts": ts,
                "thread_ts": thread_ts,
                "user_id": user_id or "unknown",
                "user_display_name": user_display,
                "user": user_label,
                "text": text,
                "channel": channel_value or channel,
            }
        )

    if canonical_thread_ts and earliest_ts is None:
        earliest_ts = _parse_slack_ts(canonical_thread_ts)

    return normalized, canonical_thread_ts, earliest_ts, channel


def _build_thread_title(thread_ts: str | None, channel: str | None) -> str:
    if thread_ts and channel:
        return f"thread-{channel}-{thread_ts}"
    if thread_ts:
        return f"thread-{thread_ts}"
    if channel:
        return f"thread-{channel}"
    return "thread"
