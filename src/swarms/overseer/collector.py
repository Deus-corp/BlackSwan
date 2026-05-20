"""State collection and normalization for the overseer."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any, Dict, Iterable, List, Set

try:
    import psutil
except ImportError:  # pragma: no cover
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
    """Converts CRDT state into a compact, normalized snapshot."""

    def __init__(self, state_source: StateSource) -> None:
        self._state_source = state_source

    def collect(self) -> SwarmSnapshot:
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
            trade_capital=sum(float(h.get("capital", 0.0)) for h in trade_recent),
            trade_dq=self._avg([float(h.get("dq", 0.0)) for h in trade_recent]),
            trade_fitness=self._avg([float(h.get("fitness", 0.0)) for h in trade_recent]),
            security_nodes=len(security_recent),
            blocked_ips=sum(int(h.get("blocked_ips", 0)) for h in security_recent),
            explorer_nodes=len(explorer_recent),
            recent_findings=self._count_recent(events, "explorer_finding", now, FINDINGS_VALIDITY_SECONDS),
            recent_vulnerability_alerts=self._count_recent(
                events, "vulnerability_alert", now, VULNERABILITY_VALIDITY_SECONDS
            ),
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
        _seen: Set[int] | None = None,
    ) -> Iterable[Dict[str, Any]]:
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
        event_type = payload.get("type")
        timestamp = payload.get("timestamp")
        return isinstance(event_type, str) and timestamp is not None

    @staticmethod
    def _latest_by_node(events: List[Dict[str, Any]], event_type: str) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for event in events:
            if event.get("type") != event_type:
                continue
            node_id = event.get("node_id")
            if not node_id:
                continue
            ts = float(event.get("timestamp", 0.0))
            current = latest.get(node_id)
            if current is None or ts >= float(current.get("timestamp", 0.0)):
                latest[node_id] = event
        return latest

    @staticmethod
    def _recent_records(
        records: Iterable[Dict[str, Any]],
        now: float,
        validity_seconds: int,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for record in records:
            ts = float(record.get("timestamp", 0.0))
            if now - ts <= validity_seconds:
                out.append(record)
        return out

    @staticmethod
    def _count_recent(
        events: List[Dict[str, Any]],
        event_type: str,
        now: float,
        validity_seconds: int,
    ) -> int:
        count = 0
        for event in events:
            if event.get("type") != event_type:
                continue
            ts = float(event.get("timestamp", 0.0))
            if now - ts <= validity_seconds:
                count += 1
        return count

    @staticmethod
    def _stale_nodes(
        latest_by_node: Dict[str, Dict[str, Any]],
        now: float,
        threshold_seconds: int,
    ) -> List[str]:
        stale: List[str] = []
        for node_id, record in latest_by_node.items():
            ts = float(record.get("timestamp", 0.0))
            if now - ts > threshold_seconds:
                stale.append(node_id)
        return stale

    @staticmethod
    def _avg(values: List[float]) -> float:
        return sum(values) / max(len(values), 1)

    @staticmethod
    def _get_resource_context() -> str:
        if psutil is None:
            return "Resource data unavailable (psutil not installed)"
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return (
                f"CPU: {cpu:.1f}%, RAM: {mem.percent:.1f}% "
                f"({mem.available // (1024 * 1024)}MB free), "
                f"Disk: {disk.percent:.1f}% ({disk.free // (1024 * 1024)}MB free)"
            )
        except Exception as exc:
            logger.warning("Resource check failed: %s", exc)
            return f"Resource check failed: {exc}"