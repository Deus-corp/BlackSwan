"""State collection and normalization for the swarm overseer.

The collector supports both legacy swarm records and the new canonical common
runtime records:

Legacy:
- trade_heartbeat
- security_heartbeat
- explorer_heartbeat
- explorer_finding
- vulnerability_alert

Canonical:
- swarm_heartbeat
- swarm_event
- swarm_command
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
except ImportError:
    psutil = None

from src.swarms.common import (
    normalize_event,
    normalize_heartbeat,
)
from src.swarms.overseer.overseer_core.interfaces import StateSource
from src.swarms.overseer.overseer_core.models import SwarmSnapshot

logger = logging.getLogger(__name__)

TRADE_HEARTBEAT_VALIDITY_SECONDS = 600
SECURITY_HEARTBEAT_VALIDITY_SECONDS = 600
EXPLORER_HEARTBEAT_VALIDITY_SECONDS = 600
IMPROVER_HEARTBEAT_VALIDITY_SECONDS = 1800

FINDINGS_VALIDITY_SECONDS = 1800
VULNERABILITY_VALIDITY_SECONDS = 1800
STALE_NODE_THRESHOLD_SECONDS = 180

MAX_EVENT_SCAN_DEPTH = 6


class StateCollector:
    """Converts CRDT state into a compact, normalized swarm snapshot."""

    def __init__(self, state_source: StateSource) -> None:
        self._state_source = state_source

    def collect(self) -> SwarmSnapshot:
        """Aggregate current CRDT state and compute swarm-level metrics."""
        state = self._state_source.state
        now = time.time()

        records = list(self._iter_event_dicts(state))

        heartbeats = self._normalize_heartbeats(records)
        events = self._normalize_events(records)

        trade_hbs = self._latest_by_node(
            self._heartbeats_for_swarm(heartbeats, "trade", role="node")
        )
        security_hbs = self._latest_by_node(
            self._heartbeats_for_swarm(heartbeats, "security", role="node")
        )
        explorer_hbs = self._latest_by_node(
            self._heartbeats_for_swarm(heartbeats, "explorer", role="node")
        )

        improver_hbs = self._latest_by_node(
            self._heartbeats_for_swarm(heartbeats, "improver", role="maintenance_agent")
        )

        trade_recent = self._recent_records(
            trade_hbs.values(),
            now,
            TRADE_HEARTBEAT_VALIDITY_SECONDS,
        )
        security_recent = self._recent_records(
            security_hbs.values(),
            now,
            SECURITY_HEARTBEAT_VALIDITY_SECONDS,
        )
        explorer_recent = self._recent_records(
            explorer_hbs.values(),
            now,
            EXPLORER_HEARTBEAT_VALIDITY_SECONDS,
        )

        improver_recent = self._recent_records(
            improver_hbs.values(),
            now,
            IMPROVER_HEARTBEAT_VALIDITY_SECONDS,
        )

        return SwarmSnapshot(
            trade_nodes=len(trade_recent),
            trade_capital=sum(
                self._metric_float(h, "capital", 0.0)
                for h in trade_recent
            ),
            trade_dq=self._avg(
                [self._metric_float(h, "dq", 0.0) for h in trade_recent]
            ),
            trade_fitness=self._avg(
                [self._metric_float(h, "fitness", 0.0) for h in trade_recent]
            ),
            security_nodes=len(security_recent),
            blocked_ips=sum(
                self._metric_int(h, "blocked_ips", 0)
                for h in security_recent
            ),
            explorer_nodes=len(explorer_recent),
            recent_findings=self._count_recent_events(
                events,
                event_type="explorer_finding",
                swarm="explorer",
                now=now,
                validity=FINDINGS_VALIDITY_SECONDS,
            ),
            recent_vulnerability_alerts=self._count_recent_events(
                events,
                event_type="vulnerability_alert",
                swarm="security",
                now=now,
                validity=VULNERABILITY_VALIDITY_SECONDS,
            ),

            improver_nodes=len(improver_recent),
            improver_files_processed=sum(
                self._metric_int(h, "files_processed", 0)
                for h in improver_recent
            ),
            improver_files_improved=sum(
                self._metric_int(h, "files_improved", 0)
                for h in improver_recent
            ),
            improver_files_quarantined=sum(
                self._metric_int(h, "files_quarantined", 0)
                for h in improver_recent
            ),
            improver_files_failed=sum(
                self._metric_int(h, "files_failed", 0)
                for h in improver_recent
            ),
            improver_last_cycle_duration_seconds=max(
                [self._metric_float(h, "last_cycle_duration_seconds", 0.0) for h in improver_recent],
                default=0.0,
            ),
            improver_last_error_count=sum(
                1
                for h in improver_recent
                if str(self._record_metrics(h).get("last_error", "") or "").strip()
            ),

            resources=self._get_resource_context(),
            stale_trade_nodes=self._stale_nodes(
                trade_hbs,
                now,
                STALE_NODE_THRESHOLD_SECONDS,
            ),
            stale_security_nodes=self._stale_nodes(
                security_hbs,
                now,
                STALE_NODE_THRESHOLD_SECONDS,
            ),
            stale_explorer_nodes=self._stale_nodes(
                explorer_hbs,
                now,
                STALE_NODE_THRESHOLD_SECONDS,
            ),
            stale_improver_nodes=self._stale_nodes(
                improver_hbs,
                now,
                STALE_NODE_THRESHOLD_SECONDS,
            ),
        )

    # ------------------------------------------------------------------
    # Raw record traversal
    # ------------------------------------------------------------------

    def _iter_event_dicts(
        self,
        payload: Any,
        *,
        _depth: int = 0,
        _seen: Optional[Set[int]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Recursively traverse state and extract mapping records."""
        if _seen is None:
            _seen = set()

        if _depth > MAX_EVENT_SCAN_DEPTH:
            return

        if isinstance(payload, Mapping):
            obj_id = id(payload)
            if obj_id in _seen:
                return
            _seen.add(obj_id)

            if self._looks_like_record(payload):
                yield dict(payload)

            for value in payload.values():
                yield from self._iter_event_dicts(
                    value,
                    _depth=_depth + 1,
                    _seen=_seen,
                )

        elif isinstance(payload, (list, tuple, set)):
            for value in payload:
                yield from self._iter_event_dicts(
                    value,
                    _depth=_depth + 1,
                    _seen=_seen,
                )

    @staticmethod
    def _looks_like_record(payload: Mapping[str, Any]) -> bool:
        """Return True if a mapping resembles a CRDT record."""
        return isinstance(payload.get("type"), str) or payload.get("timestamp") is not None

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_heartbeats(
        self,
        records: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Normalize canonical and legacy heartbeat records."""
        normalized: List[Dict[str, Any]] = []

        for record in records:
            record_type = str(record.get("type", ""))

            if record_type not in {
                "swarm_heartbeat",
                "trade_heartbeat",
                "security_heartbeat",
                "explorer_heartbeat",
                "overseer_heartbeat",
                "meta_heartbeat",
            }:
                continue

            try:
                heartbeat = normalize_heartbeat(record)
            except Exception as exc:
                logger.debug("Heartbeat normalization skipped: %s", exc)
                continue

            normalized.append(heartbeat)

        return normalized

    def _normalize_events(
        self,
        records: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Normalize canonical and legacy event records."""
        normalized: List[Dict[str, Any]] = []

        for record in records:
            record_type = str(record.get("type", ""))

            if record_type in {
                "swarm_heartbeat",
                "trade_heartbeat",
                "security_heartbeat",
                "explorer_heartbeat",
                "overseer_heartbeat",
                "meta_heartbeat",
                "swarm_command",
                "sec_command",
                "meta_command_json",
                "explorer_command",
                "trade_command",
            }:
                continue

            try:
                event = normalize_event(record)
            except Exception as exc:
                logger.debug("Event normalization skipped: %s", exc)
                continue

            normalized.append(event)

        return normalized

    @staticmethod
    def _heartbeats_for_swarm(
        heartbeats: Iterable[Dict[str, Any]],
        swarm: str,
        role: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        for heartbeat in heartbeats:
            if str(heartbeat.get("swarm", "")) != swarm:
                continue

            if role is not None and str(heartbeat.get("role", "")) != role:
                continue

            out.append(heartbeat)

        return out

    @staticmethod
    def _latest_by_node(
        heartbeats: Iterable[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Keep only the latest heartbeat per node_id."""
        latest: Dict[str, Dict[str, Any]] = {}

        for heartbeat in heartbeats:
            node_id = str(
                heartbeat.get("node_id")
                or heartbeat.get("agent_id")
                or ""
            )

            if not node_id:
                continue

            ts = StateCollector._record_timestamp(heartbeat)

            previous = latest.get(node_id)
            if previous is None or ts >= StateCollector._record_timestamp(previous):
                latest[node_id] = heartbeat

        return latest

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_timestamp(record: Mapping[str, Any]) -> float:
        try:
            return float(record.get("timestamp", 0.0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _record_metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
        metrics = record.get("metrics")
        if isinstance(metrics, Mapping):
            return metrics
        return {}

    @classmethod
    def _metric_float(
        cls,
        record: Mapping[str, Any],
        key: str,
        default: float = 0.0,
    ) -> float:
        metrics = cls._record_metrics(record)

        value = metrics.get(key, record.get(key, default))

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _metric_int(
        cls,
        record: Mapping[str, Any],
        key: str,
        default: int = 0,
    ) -> int:
        metrics = cls._record_metrics(record)

        value = metrics.get(key, record.get(key, default))

        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _recent_records(
        records: Iterable[Dict[str, Any]],
        now: float,
        validity: int,
    ) -> List[Dict[str, Any]]:
        """Return records inside a validity window."""
        recent: List[Dict[str, Any]] = []

        for record in records:
            ts = StateCollector._record_timestamp(record)
            if now - ts <= validity:
                recent.append(record)

        return recent

    @staticmethod
    def _count_recent_events(
        events: Iterable[Dict[str, Any]],
        *,
        event_type: str,
        swarm: str,
        now: float,
        validity: int,
    ) -> int:
        """Count recent normalized events by type and swarm."""
        count = 0

        for event in events:
            current_type = str(event.get("event_type", ""))
            source_swarm = str(event.get("source_swarm", ""))

            if current_type != event_type:
                continue

            if swarm and source_swarm and source_swarm != swarm:
                continue

            ts = StateCollector._record_timestamp(event)
            if now - ts <= validity:
                count += 1

        return count

    @staticmethod
    def _stale_nodes(
        latest: Dict[str, Dict[str, Any]],
        now: float,
        threshold: int,
    ) -> List[str]:
        """Identify nodes that have not heartbeated recently."""
        stale: List[str] = []

        for node_id, record in latest.items():
            ts = StateCollector._record_timestamp(record)
            if now - ts > threshold:
                stale.append(node_id)

        return stale

    @staticmethod
    def _avg(values: List[float]) -> float:
        """Calculate arithmetic mean."""
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _get_resource_context() -> str:
        """Collect system resource usage."""
        if not psutil:
            return "Resource data unavailable (psutil not installed)"

        try:
            cpu = psutil.cpu_percent(interval=None)
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