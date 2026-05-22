#!/usr/bin/env python3

from __future__ import annotations

from typing import Any, Dict, List

from .models import SecurityHeartbeat, SecurityIncident


class SecurityCollector:
    def __init__(self, crdt) -> None:
        self.crdt = crdt

    def collect_heartbeats(self) -> List[SecurityHeartbeat]:
        result: List[SecurityHeartbeat] = []

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") != "security_heartbeat":
                continue

            result.append(
                SecurityHeartbeat(
                    node_id=str(value.get("node_id") or "unknown"),
                    source_gid=str(value.get("gid") or "unknown"),
                    blocked_ips=int(value.get("blocked_ips", 0)),
                    status=str(value.get("status", "unknown")),
                    timestamp=float(value.get("timestamp", 0.0)),
                    provenance=value.get("provenance", {}),
                )
            )

        return result

    def collect_incidents(self) -> List[SecurityIncident]:
        result: List[SecurityIncident] = []

        valid_types = {
            "file_integrity_alert",
            "vulnerability_alert",
            "open_ports_detected",
            "ip_blocked",
            "all_ips_unblocked",
        }

        for value in self.crdt.state.values():
            if not isinstance(value, dict):
                continue

            if value.get("type") not in valid_types:
                continue

            result.append(
                SecurityIncident(
                    event_gid=str(value.get("gid") or "unknown"),
                    source_gid=str(value.get("source_gid") or "unknown"),
                    parent_gid=value.get("parent_gid"),
                    incident_type=str(value.get("type")),
                    severity=self._severity(value),
                    details=dict(value),
                    timestamp=float(value.get("timestamp", 0.0)),
                    provenance=value.get("provenance", {}),
                )
            )

        return result

    def _severity(self, payload: Dict[str, Any]) -> float:
        t = str(payload.get("type", ""))

        if t == "file_integrity_alert":
            return 0.95

        if t == "vulnerability_alert":
            return 0.90

        if t == "open_ports_detected":
            return 0.55

        return 0.50