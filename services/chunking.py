from __future__ import annotations

import json
from typing import Any, List, Mapping, Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter, RecursiveJsonSplitter


def chunk_content(
    content: str,
    *,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: List[str] | None = None,
) -> List[str]:
    """Chunk text using LangChain's RecursiveCharacterTextSplitter."""
    if not content:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators
        or [
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )
    docs = splitter.create_documents([content])
    return [d.page_content.strip() for d in docs if d.page_content.strip()]


def chunk_document(content: str, *, chunk_size: int = 2000, chunk_overlap: int = 50) -> List[str]:
    """Chunk a generic document/string."""
    return chunk_content(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def chunk_thread(
    messages: Sequence[Mapping[str, Any]],
    *,
    chunk_size: int = 1500,
    thread_ts: str | None = None,
    channel: str | None = None,
) -> List[dict[str, Any]]:
    """
    Chunk a Slack-like thread represented as a list of message dicts.

    Messages are kept intact (no splitting inside a message). We use LangChain's
    RecursiveJsonSplitter to break a JSON representation into size-bounded chunks and
    track the first timestamp per chunk for downstream ordering/reference_time.
    """
    if not messages:
        return []

    # Serialize messages to keep them atomic during JSON splitting.
    message_strings: dict[str, str] = {
        str(i): json.dumps(msg, ensure_ascii=False) for i, msg in enumerate(messages)
    }

    splitter = RecursiveJsonSplitter(max_chunk_size=chunk_size)
    payload = {
        "thread_ts": thread_ts,
        "channel": channel,
        "messages": message_strings,
    }
    chunk_dicts = splitter.split_json(payload, convert_lists=False)

    chunks: list[dict[str, Any]] = []
    for chunk in chunk_dicts:
        messages_obj = chunk.get("messages") or {}
        indices: list[int] = []
        if isinstance(messages_obj, dict):
            for key in messages_obj.keys():
                try:
                    indices.append(int(key))
                except (ValueError, TypeError):
                    continue
        indices.sort()
        included_messages = [messages[i] for i in indices if i < len(messages)]
        first_ts = next(
            (
                m.get("ts") or m.get("timestamp")
                for m in included_messages
                if m.get("ts") or m.get("timestamp")
            ),
            None,
        )
        chunks.append(
            {
                "text": json.dumps(chunk, ensure_ascii=False),
                "first_ts": first_ts,
                "messages": included_messages,
            }
        )

    return chunks
