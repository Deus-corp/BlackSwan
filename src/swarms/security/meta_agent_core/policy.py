#!/usr/bin/env python3

from __future__ import annotations

from typing import List

from src.swarms.security.node_core import SecurityPolicy

from .models import (
    SecurityDecision,
    SecurityHeartbeat,
    SecurityIncident,
)


class SecurityPolicyEngine:
    def __init__(self, policy: SecurityPolicy) -> None:
        self.policy = policy

    def evaluate(
        self,
        heartbeats: List[SecurityHeartbeat],
        incidents: List[SecurityIncident],
    ) -> SecurityDecision:
        blocked_ips = sum(h.blocked_ips for h in heartbeats)

        max_severity = max(
            (incident.severity for incident in incidents),
            default=0.0,
        )

        if (
            max_severity >= 0.95
            and self.policy.allow_emergency_flush_input
        ):
            return SecurityDecision(
                decision="EMERGENCY_FLUSH_INPUT",
                confidence=0.95,
                rationale="Critical integrity event detected.",
                incidents=incidents,
            )

        if blocked_ips <= self.policy.max_blocked_ips:
            return SecurityDecision(
                decision="MAINTAIN",
                confidence=0.84,
                rationale="Security posture stable.",
                incidents=incidents,
            )

        return SecurityDecision(
            decision="UNBLOCK_ALL",
            confidence=0.72,
            rationale="Blocked IP threshold exceeded.",
            incidents=incidents,
        )