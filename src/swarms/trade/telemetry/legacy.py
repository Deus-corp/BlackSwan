from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple


class Telemetry:
    """Legacy compatibility layer for telemetry. This class provides a simple interface for logging heartbeat events"""

    def __init__(
        self,
        node_id: str,
        event_store: Any,
        telegram: Any = None,
        clock: Callable[[], Tuple[int, int]] | None = None,
        notifier: Callable[[Any], Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.event_store = event_store
        self.telegram = telegram
        self.clock = clock
        self.notifier = notifier

    def heartbeat(
        self,
        step: int,
        capital: float,
        dq: float,
        fitness: float,
        liveness: float,
        active_nodes: int,
        stale_nodes: int,
        niche_counts: Dict[str, int],
        trace_id: str,
    ) -> Dict[str, Any]:
        event = {
            "type": "heartbeat",
            "node_id": self.node_id,
            "timestamp": time.time(),
            "payload": {
                "step": step,
                "capital": capital,
                "dq": dq,
                "fitness": fitness,
                "liveness": liveness,
                "active_nodes": active_nodes,
                "stale_nodes": stale_nodes,
                "niche_counts": dict(niche_counts),
                "trace_id": trace_id,
            },
        }

        if hasattr(self.event_store, "append"):
            self.event_store.append(event)

        if self.notifier:
            try:
                self.notifier(event)
            except Exception:
                pass

        return event
