"""Deterministic policy engine for overseer decisions with resource-aware validation."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

try:
    import psutil
except ImportError:
    psutil = None

from .models import OverseerDecision, SwarmSnapshot

TRADE_DQ_HIGH_THRESHOLD: Final = 0.25
TRADE_CAPITAL_LOW_THRESHOLD: Final = 2000.0
BLOCKED_IPS_HIGH_THRESHOLD: Final = 50
EXPLORE_FINDINGS_STOP_THRESHOLD: Final = 100
MIN_FREE_RAM_MB_TO_SPAWN: Final = 500
CPU_MAX_PERCENT_TO_SPAWN: Final = 85.0

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Applies hard rules and merges them with soft LLM suggestions."""

    def evaluate_hard_rules(self, snapshot: SwarmSnapshot) -> OverseerDecision:
        """Evaluates current state against hard-coded safety and operational constraints."""
        reasons: list[str] = []
        reduce_risk = False

        if snapshot.trade_dq > TRADE_DQ_HIGH_THRESHOLD:
            reduce_risk = True
            reasons.append(f"trade_dq={snapshot.trade_dq:.4f} > {TRADE_DQ_HIGH_THRESHOLD}")

        if snapshot.trade_capital < TRADE_CAPITAL_LOW_THRESHOLD:
            reduce_risk = True
            reasons.append(f"trade_capital={snapshot.trade_capital:.2f} < {TRADE_CAPITAL_LOW_THRESHOLD}")

        if snapshot.recent_vulnerability_alerts > 0:
            reduce_risk = True
            reasons.append(f"vulnerabilities={snapshot.recent_vulnerability_alerts} > 0")

        unblock_ips = snapshot.blocked_ips > BLOCKED_IPS_HIGH_THRESHOLD
        if unblock_ips:
            reasons.append(f"blocked_ips={snapshot.blocked_ips} > {BLOCKED_IPS_HIGH_THRESHOLD}")

        continue_explorer = snapshot.recent_findings <= EXPLORE_FINDINGS_STOP_THRESHOLD
        if not continue_explorer:
            reasons.append(f"findings={snapshot.recent_findings} > {EXPLORE_FINDINGS_STOP_THRESHOLD}")

        spawn_nodes = self._can_spawn_nodes()
        reasons.append("resource_check_allows_spawn" if spawn_nodes else "resource_check_blocks_spawn")

        return OverseerDecision(
            reduce_risk=reduce_risk,
            unblock_ips=unblock_ips,
            spawn_nodes=spawn_nodes,
            continue_explorer=continue_explorer,
            reason="; ".join(reasons),
            source="hard",
            confidence=1.0,
        )

    def merge(
        self,
        hard_rules: OverseerDecision,
        llm_suggestions: Mapping[str, Any] | None,
    ) -> OverseerDecision:
        """Merges hard rules with LLM suggestions, prioritizing safety and resource constraints."""
        suggestions = self._normalize_suggestions(llm_suggestions)

        if not suggestions:
            return hard_rules

        reduce_risk = hard_rules.reduce_risk or suggestions.get("reduce_risk", False)
        increase_exploration = suggestions.get("increase_exploration", False) and not hard_rules.reduce_risk
        unblock_ips = hard_rules.unblock_ips and suggestions.get("unblock_ips", False)
        spawn_nodes = hard_rules.spawn_nodes and suggestions.get("spawn_nodes", False)
        continue_explorer = hard_rules.continue_explorer and suggestions.get("continue_explorer", True)

        reason = f"{hard_rules.reason} | llm_suggestions={suggestions}"

        return OverseerDecision(
            reduce_risk=reduce_risk,
            increase_exploration=increase_exploration,
            unblock_ips=unblock_ips,
            spawn_nodes=spawn_nodes,
            continue_explorer=continue_explorer,
            reason=reason,
            source="merged",
            confidence=0.5,
        )

    @staticmethod
    def _normalize_suggestions(llm_suggestions: Mapping[str, Any] | None) -> dict[str, bool]:
        """Sanitizes and casts LLM suggestions into a typed dictionary."""
        if not llm_suggestions:
            return {}

        keys = {"reduce_risk", "increase_exploration", "unblock_ips", "spawn_nodes", "continue_explorer"}
        return {k: bool(llm_suggestions.get(k, False)) for k in keys}

    @staticmethod
    def _can_spawn_nodes() -> bool:
        """Checks system resources for spawning capability."""
        if psutil is None:
            return False

        try:
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.0)
            ram_free_mb = mem.available // (1024 * 1024)
            return ram_free_mb >= MIN_FREE_RAM_MB_TO_SPAWN and cpu < CPU_MAX_PERCENT_TO_SPAWN
        except (RuntimeError, PermissionError, ValueError) as exc:
            logger.error("Resource check failed: %s", exc)
            return False