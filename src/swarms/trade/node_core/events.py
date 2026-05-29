"""Trade node event emission helpers."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from src.core.events import Event


async def emit_trade_event(
    *,
    event_bus: Any,
    event_store: Any,
    crdt: Any,
    node_id: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    parent_id: str | None = None,
) -> Event:
    """Emit a trade event to event bus, event store, and CRDT when available."""
    safe_payload = dict(payload or {})
    trace_id = str(safe_payload.get("trace_id") or parent_id or uuid.uuid4().hex)

    event_payload = {
        **safe_payload,
        "trace_id": trace_id,
    }

    event = Event.create(
        node_id=node_id,
        event_type=event_type,
        payload=event_payload,
        parent_id=parent_id,
    )

    if event_bus is not None and hasattr(event_bus, "publish"):
        await event_bus.publish(event)

    if event_store is not None and hasattr(event_store, "append"):
        event_store.append(event)

    if crdt is not None and hasattr(crdt, "add_genome"):
        await crdt.add_genome(
            {
                "type": "swarm_event",
                "event_type": event_type,
                "source_node": node_id,
                "payload": event_payload,
                "parent_id": parent_id,
                "timestamp": event.ts,
                "event_id": event.event_id,
            }
        )

    return event


__all__ = ["emit_trade_event"]