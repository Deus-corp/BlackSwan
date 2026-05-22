#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class SecurityHeartbeat:
    node_id: str
    source_gid: str
    blocked_ips: int
    status: str
    timestamp: float
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SecurityIncident:
    event_gid: str
    source_gid: str
    parent_gid: Optional[str]
    incident_type: str
    severity: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SecurityDecision:
    decision: str
    confidence: float
    rationale: str
    incidents: List[SecurityIncident] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)