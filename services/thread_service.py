from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.ext.asyncio import AsyncSession
from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode, EpisodeType

from infrastructure.repositories import DataRepository, ChunkRepository, GraphitiEpisodeRepository
from services.chunking import chunk_thread
from infrastructure.graphiti import (
    DEFAULT_ENTITY_TYPES,
    DEFAULT_EDGE_TYPES,
    DEFAULT_EDGE_TYPE_MAP,
    build_group_id,
)

logger = logging.getLogger(__name__)
THREAD_UUID_NAMESPACE = uuid5(NAMESPACE_URL, "graphiti-thread-anchor")


class ThreadService:
    """Service to ingest Slack-like threads, store chunks, and send to Graphiti."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
        graphiti_client: Graphiti | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data_repo = DataRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.graphiti_episode_repo = GraphitiEpisodeRepository(session)
        self.graphiti_client = graphiti_client

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

        graph_entities: dict[str, EntityNode] = {}
        graph_edges: dict[str, EntityEdge] = {}
        invalidated_edges: dict[str, EntityEdge] = {}

        if self.graphiti_client:
            try:
                thread_key = _build_thread_key(canonical_thread_ts, channel)
                group_id = build_group_id(self.tenant_id, self.user_id)
                episode_uuids: list[str] = []
                for idx, chunk in enumerate(chunks):
                    chunk_ref = _parse_slack_ts(chunk.get("first_ts")) or earliest_ts or datetime.now(timezone.utc)
                    chunk_payload = {
                        "thread_ts": canonical_thread_ts,
                        "channel": channel,
                        "messages": chunk.get("messages") or [],
                    }
                    result = await self.graphiti_client.add_episode(
                        name=f"thread-{record.id}-chunk-{idx}",
                        episode_body=json.dumps(chunk_payload, ensure_ascii=False),
                        source=EpisodeType.json,
                        source_description="slack_thread",
                        reference_time=chunk_ref,
                        group_id=group_id,
                        entity_types=DEFAULT_ENTITY_TYPES,
                        edge_types=DEFAULT_EDGE_TYPES,
                        edge_type_map=DEFAULT_EDGE_TYPE_MAP,
                    )
                    for node in result.nodes:
                        graph_entities[node.uuid] = node
                    for edge in result.edges:
                        graph_edges[edge.uuid] = edge
                        if edge.invalid_at or edge.expired_at:
                            invalidated_edges[edge.uuid] = edge
                    episode_uuids.append(result.episode.uuid)
                    await _attach_thread_context(
                        client=self.graphiti_client,
                        thread_key=thread_key,
                        channel=channel,
                        thread_ts=canonical_thread_ts,
                        reference_time=chunk_ref,
                        group_id=group_id,
                        entities=result.nodes,
                        episode_uuid=result.episode.uuid,
                    )
                await self.graphiti_episode_repo.create_batch(
                    data_id=record.id,
                    episode_uuids=episode_uuids,
                )
            except Exception as exc:
                logger.warning("Graphiti ingestion failed for thread-%s: %s", record.id, exc)
                raise
        await self.session.flush()
        return {
            "id": record.id,
            "title": record.title,
            "body": record.body,
            "chunk_count": len(chunks),
            "graph_entities": [node.model_dump() for node in graph_entities.values()] or None,
            "graph_edges": [edge.model_dump() for edge in graph_edges.values()] or None,
            "invalidated_edges": [edge.model_dump() for edge in invalidated_edges.values()] or None,
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


def _build_thread_key(thread_ts: str | None, channel: str | None) -> str | None:
    if thread_ts:
        return f"{thread_ts}|{channel or ''}".strip("|")
    return None


def _build_thread_title(thread_ts: str | None, channel: str | None) -> str:
    if thread_ts and channel:
        return f"thread-{channel}-{thread_ts}"
    if thread_ts:
        return f"thread-{thread_ts}"
    if channel:
        return f"thread-{channel}"
    return "thread"


def _thread_uuid(group_id: str, thread_key: str) -> str:
    # Deterministic UUID to avoid duplicating the same thread node within a group.
    return str(uuid5(THREAD_UUID_NAMESPACE, f"{group_id}:{thread_key}"))


async def _attach_thread_context(
    *,
    client: Graphiti,
    thread_key: str | None,
    channel: str | None,
    thread_ts: str | None,
    reference_time: datetime,
    group_id: str,
    entities: Sequence[EntityNode],
    episode_uuid: str,
) -> None:
    if not thread_key:
        return
    thread_node = EntityNode(
        uuid=_thread_uuid(group_id, thread_key),
        name=f"thread-{thread_key}",
        group_id=group_id,
        labels=["Thread"],
        attributes={
            "thread_key": thread_key,
            "thread_ts": thread_ts,
            "channel": channel,
            "start_time": reference_time.isoformat(),
        },
    )

    seen_entities: set[str] = set()
    for entity in entities:
        if entity.uuid in seen_entities:
            continue
        seen_entities.add(entity.uuid)
        edge = EntityEdge(
            group_id=group_id,
            source_node_uuid=entity.uuid,
            target_node_uuid=thread_node.uuid,
            name="mentioned_in_thread",
            fact=f"{entity.name} mentioned in thread {thread_key}",
            episodes=[episode_uuid],
            created_at=reference_time,
            valid_at=reference_time,
        )
        await client.add_triplet(entity, edge, thread_node)
