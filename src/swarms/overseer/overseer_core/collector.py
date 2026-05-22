"""State collection and normalization for the swarm overseer."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
except ImportError:
    psutil = None

from .interfaces import StateSource
from .models import SwarmSnapshot

logger = logging.getLogger(__name__)

TRADE_HEARTBEAT_VALIDITY_SECONDS = 600
SECURITY_HEARTBEAT_VALIDITY_SECONDS = 600
EXPLORER_HEARTBEAT_VALIDITY_SECONDS = 600
FINDINGS_VALIDITY_SECONDS = 1800
VULNERABILITY_VALIDITY_SECONDS = 1800
STALE_NODE_THRESHOLD_SECONDS = 180
MAX_EVENT_SCAN_DEPTH = 5


class StateCollector:
    """Converts CRDT state into a compact, normalized swarm snapshot."""

    def __init__(self, state_source: StateSource) -> None:
        self._state_source = state_source

    def collect(self) -> SwarmSnapshot:
        """Aggregates current state and computes swarm metrics."""
        state = self._state_source.state
        now = time.time()
        events = list(self._iter_event_dicts(state))

        trade_hbs = self._latest_by_node(events, "trade_heartbeat")
        security_hbs = self._latest_by_node(events, "security_heartbeat")
        explorer_hbs = self._latest_by_node(events, "explorer_heartbeat")

        trade_recent = self._recent_records(trade_hbs.values(), now, TRADE_HEARTBEAT_VALIDITY_SECONDS)
        security_recent = self._recent_records(security_hbs.values(), now, SECURITY_HEARTBEAT_VALIDITY_SECONDS)
        explorer_recent = self._recent_records(explorer_hbs.values(), now, EXPLORER_HEARTBEAT_VALIDITY_SECONDS)

        return SwarmSnapshot(
            trade_nodes=len(trade_recent),
            trade_capital=sum(self._safe_float(h.get("capital", 0.0)) for h in trade_recent),
            trade_dq=self._avg([self._safe_float(h.get("dq", 0.0)) for h in trade_recent]),
            trade_fitness=self._avg([self._safe_float(h.get("fitness", 0.0)) for h in trade_recent]),
            security_nodes=len(security_recent),
            blocked_ips=sum(self._safe_int(h.get("blocked_ips", 0)) for h in security_recent),
            explorer_nodes=len(explorer_recent),
            recent_findings=self._count_recent(events, "explorer_finding", now, FINDINGS_VALIDITY_SECONDS),
            recent_vulnerability_alerts=self._count_recent(events, "vulnerability_alert", now, VULNERABILITY_VALIDITY_SECONDS),
            resources=self._get_resource_context(),
            stale_trade_nodes=self._stale_nodes(trade_hbs, now, STALE_NODE_THRESHOLD_SECONDS),
            stale_security_nodes=self._stale_nodes(security_hbs, now, STALE_NODE_THRESHOLD_SECONDS),
            stale_explorer_nodes=self._stale_nodes(explorer_hbs, now, STALE_NODE_THRESHOLD_SECONDS),
        )

    def _iter_event_dicts(
        self,
        payload: Any,
        *,
        _depth: int = 0,
        _seen: Optional[Set[int]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Recursively traverses state to extract event-like dictionaries."""
        if _seen is None:
            _seen = set()

        if _depth > MAX_EVENT_SCAN_DEPTH:
            return

        if isinstance(payload, Mapping):
            obj_id = id(payload)
            if obj_id in _seen:
                return
            _seen.add(obj_id)

            if self._looks_like_event(payload):
                yield dict(payload)

            for value in payload.values():
                yield from self._iter_event_dicts(value, _depth=_depth + 1, _seen=_seen)

        elif isinstance(payload, (list, tuple, set)):
            for value in payload:
                yield from self._iter_event_dicts(value, _depth=_depth + 1, _seen=_seen)

    @staticmethod
    def _looks_like_event(payload: Mapping[str, Any]) -> bool:
        """Validates if a mapping represents a structural event."""
        return isinstance(payload.get("type"), str) and payload.get("timestamp") is not None

    @staticmethod
    def _latest_by_node(events: Iterable[Dict[str, Any]], event_type: str) -> Dict[str, Dict[str, Any]]:
        """Filters events to keep only the latest per node_id."""
        latest: Dict[str, Dict[str, Any]] = {}
        for event in events:
            if event.get("type") != event_type:
                continue

            node_id = event.get("node_id")
            if not node_id or not isinstance(node_id, str):
                continue

            ts = StateCollector._safe_float(event.get("timestamp", 0.0))
            if node_id not in latest or ts >= StateCollector._safe_float(latest[node_id].get("timestamp", 0.0)):
                latest[node_id] = event

        return latest

    @staticmethod
    def _recent_records(records: Iterable[Dict[str, Any]], now: float, validity: int) -> List[Dict[str, Any]]:
        """Filters records within a validity window."""
        return [r for r in records if now - StateCollector._safe_float(r.get("timestamp", 0.0)) <= validity]

    @staticmethod
    def _count_recent(events: Iterable[Dict[str, Any]], event_type: str, now: float, validity: int) -> int:
        """Counts specific event types within a timeframe."""
        return sum(
            1
            for e in events
            if e.get("type") == event_type
            and (now - StateCollector._safe_float(e.get("timestamp", 0.0)) <= validity)
        )

    @staticmethod
    def _stale_nodes(latest: Dict[str, Dict[str, Any]], now: float, threshold: int) -> List[str]:
        """Identifies nodes that haven't heartbeated recently."""
        return [
            nid
            for nid, rec in latest.items()
            if now - StateCollector._safe_float(rec.get("timestamp", 0.0)) > threshold
        ]

    @staticmethod
    def _avg(values: List[float]) -> float:
        """Calculates arithmetic mean."""
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _get_resource_context() -> str:
        """Collects system resource usage."""
        if not psutil:
            return "Resource data unavailable (psutil not installed)"

        try:
            cpu = psutil.cpu_percent(interval=0.0)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"CPU: {cpu:.1f}%, "
                f"RAM: {mem.percent:.1f}% ({mem.available // 1048576}MB free), "
                f"Disk: {disk.percent:.1f}% ({disk.free // 1048576}MB free)"
            )
        except Exception as exc:
            logger.warning("Resource check failed: %s", exc)
            return f"Resource check failed: {exc}"