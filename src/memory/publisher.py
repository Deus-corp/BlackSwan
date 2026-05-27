"""Helpers for publishing canonical memory records into shared CRDT state.

This module lets any swarm publish a memory-compatible record without knowing
how MemorySwarmNode stores or validates it. The MemorySwarmNode later ingests
these records through SharedMemoryBridge -> QuarantineBuffer -> LocalMemoryAPI.
"""

from __future__ import annotations

import time
import uuid
from typing import Any


def build_memory_record_event(
    *,
    kind: str,
    scope: str = "shared",
    payload: dict[str, Any] | Any,
    source_node_id: str,
    swarm: str,
    topic: str | None = None,
    confidence: float = 1.0,
    priority: int = 0,
    tags: list[str] | None = None,
    record_id: str | None = None,
    parents: list[str] | None = None,
    signature: str | None = None,
    verified: bool = False,
) -> dict[str, Any]:
    """Build canonical CRDT payload for shared memory ingestion."""
    clean_kind = str(kind or "").strip()
    clean_scope = str(scope or "shared").strip()
    clean_source_node_id = str(source_node_id or "").strip()
    clean_swarm = str(swarm or "").strip()

    if not clean_kind:
        raise ValueError("kind cannot be empty")
    if not clean_scope:
        raise ValueError("scope cannot be empty")
    if not clean_source_node_id:
        raise ValueError("source_node_id cannot be empty")
    if not clean_swarm:
        raise ValueError("swarm cannot be empty")

    memory_payload: dict[str, Any]
    if isinstance(payload, dict):
        memory_payload = dict(payload)
    else:
        memory_payload = {"value": payload}

    clean_tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    if clean_tags:
        existing_tags = memory_payload.get("tags", [])
        if isinstance(existing_tags, str):
            existing_tags = [existing_tags]
        if not isinstance(existing_tags, list):
            existing_tags = []
        memory_payload["tags"] = sorted(
            {
                *[str(tag).strip() for tag in existing_tags if str(tag).strip()],
                *clean_tags,
            }
        )

    safe_confidence = max(0.0, min(1.0, float(confidence)))
    safe_priority = max(0, min(100, int(priority)))

    event_id = record_id or uuid.uuid4().hex

    return {
        "type": "memory_record",
        "id": event_id,
        "kind": clean_kind,
        "scope": clean_scope,
        "topic": topic,
        "payload": memory_payload,
        "source": {
            "originNodeId": clean_source_node_id,
            "originPeerId": "",
            "swarm": clean_swarm,
            "parents": list(parents or []),
        },
        "confidence": safe_confidence,
        "priority": safe_priority,
        "signature": signature,
        "verified": bool(verified),
        "timestamp": time.time(),
    }


async def publish_memory_record(
    crdt: Any,
    *,
    kind: str,
    scope: str = "shared",
    payload: dict[str, Any] | Any,
    source_node_id: str,
    swarm: str,
    topic: str | None = None,
    confidence: float = 1.0,
    priority: int = 0,
    tags: list[str] | None = None,
    record_id: str | None = None,
    parents: list[str] | None = None,
    signature: str | None = None,
    verified: bool = False,
) -> str:
    """Publish a memory_record payload to CRDT and return record id."""
    event = build_memory_record_event(
        kind=kind,
        scope=scope,
        payload=payload,
        source_node_id=source_node_id,
        swarm=swarm,
        topic=topic,
        confidence=confidence,
        priority=priority,
        tags=tags,
        record_id=record_id,
        parents=parents,
        signature=signature,
        verified=verified,
    )

    add_genome = getattr(crdt, "add_genome", None)
    if not callable(add_genome):
        raise TypeError("crdt must expose async add_genome(payload)")

    result = add_genome(event)
    if hasattr(result, "__await__"):
        await result

    return str(event["id"])