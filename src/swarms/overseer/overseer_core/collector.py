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
import os
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
    command_event_status,
    is_command_event,
    is_lifecycle_event,
    lifecycle_event_status,
)
from src.swarms.overseer.overseer_core.interfaces import StateSource
from src.swarms.overseer.overseer_core.models import SwarmSnapshot
from src.swarms.common import SWARM_TOPOLOGY

logger = logging.getLogger(__name__)

def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default

    return max(minimum, value)

TRADE_HEARTBEAT_VALIDITY_SECONDS = 600
SECURITY_HEARTBEAT_VALIDITY_SECONDS = 600
EXPLORER_HEARTBEAT_VALIDITY_SECONDS = 600
IMPROVER_HEARTBEAT_VALIDITY_SECONDS = 1800
GENERIC_HEARTBEAT_VALIDITY_SECONDS = 600

FINDINGS_VALIDITY_SECONDS = 1800
VULNERABILITY_VALIDITY_SECONDS = 1800
STALE_NODE_THRESHOLD_SECONDS = 180

COMMAND_EVENT_WINDOW_SECONDS = _env_int(
    "OVERSEER_COMMAND_EVENT_WINDOW_SECONDS",
    15 * 60,
    minimum=60,
)

LEGACY_COMMAND_TYPES = {
    "sec_command",
    "explorer_command",
    "meta_command_json",
    "trade_command",
}

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

        latest_heartbeats_by_swarm = self._latest_heartbeats_by_swarm(heartbeats)

        recent_heartbeats_by_swarm: Dict[str, List[Dict[str, Any]]] = {}
        swarm_counts: Dict[str, int] = {}
        swarm_role_counts: Dict[str, Dict[str, int]] = {}
        stale_swarm_nodes: Dict[str, List[str]] = {}
        latest_swarm_heartbeats: Dict[str, List[Dict[str, Any]]] = {}

        for swarm_name, latest_by_node in latest_heartbeats_by_swarm.items():
            latest_records = list(latest_by_node.values())
            recent_records = self._recent_records(
                latest_records,
                now=now,
                window_seconds=GENERIC_HEARTBEAT_VALIDITY_SECONDS,
            )

            recent_heartbeats_by_swarm[swarm_name] = [dict(item) for item in recent_records]
            swarm_counts[swarm_name] = len(recent_records)
            swarm_role_counts[swarm_name] = self._role_counts(latest_records)
            stale_swarm_nodes[swarm_name] = self._stale_nodes(
                latest_by_node,
                now,
                STALE_NODE_THRESHOLD_SECONDS,
            )
            latest_swarm_heartbeats[swarm_name] = [dict(item) for item in latest_records]

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

            swarm_counts=swarm_counts,
            swarm_role_counts=swarm_role_counts,
            stale_swarm_nodes=stale_swarm_nodes,
            latest_swarm_heartbeats=latest_swarm_heartbeats,

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
    
    @staticmethod
    def _command_event_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
        """Count command/lifecycle observability events by status."""
        counts = {
            "applied": 0,
            "skipped": 0,
            "blocked": 0,
            "unsupported": 0,
            "received": 0,
            "unknown": 0,
        }

        for record in records:
            if not isinstance(record, Mapping):
                continue

            status = ""

            if is_lifecycle_event(record):
                status = lifecycle_event_status(record)
            elif is_command_event(record):
                status = command_event_status(record)
            else:
                continue

            if status in counts:
                counts[status] += 1
            else:
                counts["unknown"] += 1

        return counts

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
                "improver_heartbeat",
                "overseer_heartbeat",
                "memory_heartbeat",
                "simulation_heartbeat",
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
                "improver_heartbeat",
                "overseer_heartbeat",
                "memory_heartbeat",
                "simulation_heartbeat",
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
        events: Iterable[Dict[str, Any]],
        event_type: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Filter events to keep only the latest per node_id/agent_id."""
        latest: Dict[str, Dict[str, Any]] = {}

        for event in events:
            if event_type is not None and event.get("type") != event_type:
                continue

            node_id = (
                event.get("node_id")
                or event.get("agent_id")
                or event.get("source_node")
                or event.get("source_agent")
            )

            if not node_id or not isinstance(node_id, str):
                continue

            ts = float(event.get("timestamp", 0.0) or 0.0)

            if node_id not in latest or ts >= float(latest[node_id].get("timestamp", 0.0) or 0.0):
                latest[node_id] = event

        return latest
    
    @classmethod
    def _latest_heartbeats_by_swarm(
        cls,
        heartbeats: Iterable[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Return latest heartbeat per node grouped by swarm."""
        grouped_raw: Dict[str, List[Dict[str, Any]]] = {}

        for heartbeat in heartbeats:
            swarm = cls._record_swarm(heartbeat)
            if not swarm:
                swarm = str(heartbeat.get("swarm", "") or "")

            if not swarm:
                continue

            grouped_raw.setdefault(swarm, []).append(heartbeat)

        return {
            swarm: cls._latest_by_node(records)
            for swarm, records in grouped_raw.items()
        }

    def collect_topology_health(self) -> Dict[str, Any]:
        """Build topology-aware ecosystem health view from CRDT state.

        This is a generic view driven by SWARM_TOPOLOGY.
        It intentionally lives beside SwarmSnapshot while migration is ongoing.
        """
        state = self._state_source.state
        now = time.time()
        events = list(self._iter_event_dicts(state))

        heartbeats = [
            event
            for event in events
            if event.get("type") in {
                "swarm_heartbeat",
                "trade_heartbeat",
                "security_heartbeat",
                "explorer_heartbeat",
                "improver_heartbeat",
                "overseer_heartbeat",
                "memory_heartbeat",
                "simulation_heartbeat",
                "meta_heartbeat",
            }
        ]

        commands = [
            event
            for event in events
            if event.get("type")
            in {
                "swarm_command",
                "sec_command",
                "explorer_command",
                "meta_command_json",
                "trade_command",
            }
        ]

        recent_commands = self._recent_records(
            commands,
            now=now,
            window_seconds=COMMAND_EVENT_WINDOW_SECONDS,
        )

        legacy_command_counts = self._legacy_command_counts(recent_commands)

        swarm_events = [
            event
            for event in events
            if event.get("type")
            in {
                "swarm_event",
                "security_event",
                "explorer_finding",
                "vulnerability_alert",
            }
        ]

        recent_swarm_events = self._recent_records(
            swarm_events,
            now=now,
            window_seconds=COMMAND_EVENT_WINDOW_SECONDS,
        )

        all_command_events = self._command_event_counts(recent_swarm_events)

        swarms: Dict[str, Any] = {}

        for swarm_name, spec in SWARM_TOPOLOGY.items():
            swarm_hbs = [
                hb
                for hb in heartbeats
                if self._record_swarm(hb) == swarm_name
            ]

            latest_by_node = self._latest_by_node(swarm_hbs, event_type=None)
            role_counts = self._role_counts(latest_by_node.values())

            swarm_commands = [
                cmd
                for cmd in commands
                if self._record_target_swarm(cmd) == swarm_name
            ]

            swarm_recent_commands = self._recent_records(
                swarm_commands,
                now=now,
                window_seconds=COMMAND_EVENT_WINDOW_SECONDS,
            )

            swarm_legacy_commands = self._legacy_command_counts(swarm_recent_commands)

            swarm_related_events = [
                event
                for event in swarm_events
                if self._record_swarm(event) == swarm_name
                or self._record_target_swarm(event) == swarm_name
            ]

            swarm_recent_events = self._recent_records(
                swarm_related_events,
                now=now,
                window_seconds=COMMAND_EVENT_WINDOW_SECONDS,
            )

            latest_ts = max(
                [
                    float(item.get("timestamp", 0.0) or 0.0)
                    for item in list(latest_by_node.values())
                    + swarm_related_events
                    + swarm_commands
                ],
                default=0.0,
            )

            stale_nodes = self._stale_nodes(
                latest_by_node,
                now,
                STALE_NODE_THRESHOLD_SECONDS,
            )

            swarms[swarm_name] = {
                "description": spec.description,
                "managed_by_overseer": spec.managed_by_overseer,
                "advisory_only": spec.advisory_only,
                "known_roles": list(spec.roles.keys()),
                "node_count": len(latest_by_node),
                "role_counts": role_counts,
                "heartbeats": len(swarm_hbs),
                "events": len(swarm_related_events),
                "commands": len(swarm_commands),
                "legacy_commands": swarm_legacy_commands,
                "legacy_command_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": self._command_event_counts(swarm_recent_events),
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "latest_ts": latest_ts,
                "stale_nodes": stale_nodes,
                "status": self._topology_swarm_status(
                    node_count=len(latest_by_node),
                    stale_nodes=stale_nodes,
                    latest_ts=latest_ts,
                    now=now,
                ),
            }

        return {
            "type": "ecosystem",
            "topology_version": "v1",
            "swarm_count": len(swarms),
            "total_nodes": sum(int(data["node_count"]) for data in swarms.values()),
            "total_stale_nodes": sum(len(data["stale_nodes"]) for data in swarms.values()),
            "command_events": all_command_events,
            "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
            "legacy_commands": legacy_command_counts,
            "legacy_command_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
            "swarms": swarms,
        }


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

    @staticmethod
    def _record_swarm(record: Mapping[str, Any]) -> str:
        """Infer source swarm from canonical/legacy records."""
        if not isinstance(record, Mapping):
            return ""

        direct = record.get("swarm") or record.get("source_swarm")
        if direct:
            return str(direct)

        record_type = str(record.get("type") or "")

        legacy_type_to_swarm = {
            "sec_command": "security",
            "explorer_command": "explorer",
            "meta_command_json": "explorer",
            "trade_command": "trade",
        }

        if record_type in legacy_type_to_swarm:
            return legacy_type_to_swarm[record_type]

        if record_type in {"trade_heartbeat", "meta_command_json", "trade_command"}:
            return "trade"

        if record_type in {"security_heartbeat", "security_event", "sec_command", "vulnerability_alert"}:
            return "security"

        if record_type in {"explorer_heartbeat", "explorer_finding", "explorer_command", "explorer_targets"}:
            return "explorer"

        if record_type == "improver_heartbeat":
            return "improver"
        
        if record_type == "improver_heartbeat":
            return "improver"

        if record_type == "overseer_heartbeat":
            return "overseer"

        if record_type == "memory_heartbeat":
            return "memory"

        if record_type == "simulation_heartbeat":
            return "simulation"

        if record_type == "meta_heartbeat":
            node_id = str(record.get("node_id") or record.get("agent_id") or "")
            if node_id.startswith("exp-meta"):
                return "explorer"
            if node_id.startswith("sec-meta"):
                return "security"

        return ""

    @staticmethod
    def _record_target_swarm(record: Mapping[str, Any]) -> str:
        """Infer target swarm from canonical/legacy command/event records."""
        if not isinstance(record, Mapping):
            return ""

        direct = record.get("target_swarm")
        if direct:
            return str(direct)

        data = record.get("data") if isinstance(record.get("data"), Mapping) else {}
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}

        if data.get("swarm"):
            return str(data.get("swarm"))

        if payload.get("swarm"):
            return str(payload.get("swarm"))

        record_type = str(record.get("type") or "")

        if record_type == "sec_command":
            return "security"

        if record_type in {"explorer_command", "explorer_targets"}:
            return "explorer"

        if record_type in {"meta_command_json", "trade_command"}:
            return "trade"

        return ""

    @staticmethod
    def _record_role(record: Mapping[str, Any]) -> str:
        """Infer role from heartbeat/event record."""
        if not isinstance(record, Mapping):
            return ""

        role = record.get("role")
        if role:
            return str(role)

        record_type = str(record.get("type") or "")
        node_id = str(record.get("node_id") or record.get("agent_id") or "")

        if record_type == "meta_heartbeat" or "-meta-" in node_id:
            return "meta_agent"

        if record_type == "improver_heartbeat":
            return "maintenance_agent"

        if record_type.endswith("_heartbeat") or record_type == "swarm_heartbeat":
            return "node"

        return ""

    @classmethod
    def _role_counts(cls, records: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
        """Count latest records by inferred role."""
        counts: Dict[str, int] = {}

        for record in records:
            role = cls._record_role(record) or "unknown"
            counts[role] = counts.get(role, 0) + 1

        return counts

    @staticmethod
    def _topology_swarm_status(
        *,
        node_count: int,
        stale_nodes: List[str],
        latest_ts: float,
        now: float,
    ) -> str:
        """Compute lightweight swarm health status."""
        if node_count <= 0:
            return "absent"

        if stale_nodes and len(stale_nodes) >= node_count:
            return "stale"

        if stale_nodes:
            return "degraded"

        if latest_ts > 0 and now - latest_ts > STALE_NODE_THRESHOLD_SECONDS:
            return "stale"

        return "ok"
    
    @staticmethod
    def _recent_records(
        records: list[Mapping[str, Any]],
        now: float | None = None,
        window_seconds: float | None = None,
    ) -> list[Mapping[str, Any]]:
        """Return records whose timestamp falls within the recent window.

        Backward-compatible call styles:
        - _recent_records(records, now, window_seconds)
        - _recent_records(records, now=now, window_seconds=window)
        - _recent_records(records, now=now)  # uses STALE_NODE_THRESHOLD_SECONDS
        """
        if now is None:
            now = time.time()

        if window_seconds is None:
            window_seconds = STALE_NODE_THRESHOLD_SECONDS

        cutoff = float(now) - float(window_seconds)
        recent: list[Mapping[str, Any]] = []

        for record in records:
            if not isinstance(record, Mapping):
                continue

            try:
                ts = float(record.get("timestamp", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue

            if ts >= cutoff:
                recent.append(record)

        return recent
    
    @staticmethod
    def _legacy_command_counts(records: list[Mapping[str, Any]]) -> dict[str, int]:
        """Count legacy command records by type."""
        counts = {
            "sec_command": 0,
            "explorer_command": 0,
            "meta_command_json": 0,
            "trade_command": 0,
        }

        for record in records:
            if not isinstance(record, Mapping):
                continue

            record_type = str(record.get("type") or "")
            if record_type in counts:
                counts[record_type] += 1

        return counts