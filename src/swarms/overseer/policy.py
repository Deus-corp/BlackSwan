"""Deterministic policy engine for overseer decisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

from src.swarms.overseer.models import OverseerDecision, SwarmSnapshot

TRADE_DQ_HIGH_THRESHOLD = 0.25
TRADE_CAPITAL_LOW_THRESHOLD = 2000.0
BLOCKED_IPS_HIGH_THRESHOLD = 50
EXPLORE_FINDINGS_STOP_THRESHOLD = 100
MIN_FREE_RAM_MB_TO_SPAWN = 500
CPU_MAX_PERCENT_TO_SPAWN = 85.0


class PolicyEngine:
    """Applies hard rules and merges them with soft suggestions."""

    def evaluate_hard_rules(self, snapshot: SwarmSnapshot) -> OverseerDecision:
        reasons = []

        reduce_risk = False
        if snapshot.trade_dq > TRADE_DQ_HIGH_THRESHOLD:
            reduce_risk = True
            reasons.append(
                f"trade_dq={snapshot.trade_dq:.4f} > threshold={TRADE_DQ_HIGH_THRESHOLD:.4f}"
            )
        if snapshot.trade_capital < TRADE_CAPITAL_LOW_THRESHOLD:
            reduce_risk = True
            reasons.append(
                f"trade_capital={snapshot.trade_capital:.2f} < threshold={TRADE_CAPITAL_LOW_THRESHOLD:.2f}"
            )
        if snapshot.recent_vulnerability_alerts > 0:
            reduce_risk = True
            reasons.append(
                f"recent_vulnerability_alerts={snapshot.recent_vulnerability_alerts} > 0"
            )

        unblock_ips = snapshot.blocked_ips > BLOCKED_IPS_HIGH_THRESHOLD
        if unblock_ips:
            reasons.append(
                f"blocked_ips={snapshot.blocked_ips} > threshold={BLOCKED_IPS_HIGH_THRESHOLD}"
            )

        continue_explorer = snapshot.recent_findings <= EXPLORE_FINDINGS_STOP_THRESHOLD
        if not continue_explorer:
            reasons.append(
                f"recent_findings={snapshot.recent_findings} > stop_threshold={EXPLORE_FINDINGS_STOP_THRESHOLD}"
            )

        spawn_nodes = self._can_spawn_nodes(snapshot.resources)
        if spawn_nodes:
            reasons.append("resource_check_allows_spawn")
        else:
            reasons.append("resource_check_blocks_spawn")

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
        suggestions = self._normalize_suggestions(llm_suggestions)

        if not suggestions:
            return OverseerDecision(
                reduce_risk=hard_rules.reduce_risk,
                increase_exploration=hard_rules.increase_exploration,
                unblock_ips=hard_rules.unblock_ips,
                spawn_nodes=hard_rules.spawn_nodes,
                continue_explorer=hard_rules.continue_explorer,
                reason=hard_rules.reason,
                source="hard",
                confidence=hard_rules.confidence,
            )

        # Safety-first merge:
        # - hard rules can only be strengthened by the LLM
        # - hard resource constraints always win
        reduce_risk = hard_rules.reduce_risk or suggestions.get("reduce_risk", False)
        increase_exploration = (
            suggestions.get("increase_exploration", False) and not hard_rules.reduce_risk
        )
        unblock_ips = hard_rules.unblock_ips and suggestions.get("unblock_ips", False)
        spawn_nodes = hard_rules.spawn_nodes and suggestions.get("spawn_nodes", False)
        continue_explorer = hard_rules.continue_explorer and suggestions.get(
            "continue_explorer", True
        )

        reasons = [hard_rules.reason] if hard_rules.reason else []
        reasons.append(
            "llm_suggestions="
            + ", ".join(
                f"{key}={value}" for key, value in suggestions.items() if isinstance(value, bool)
            )
        )

        return OverseerDecision(
            reduce_risk=reduce_risk,
            increase_exploration=increase_exploration,
            unblock_ips=unblock_ips,
            spawn_nodes=spawn_nodes,
            continue_explorer=continue_explorer,
            reason=" | ".join(r for r in reasons if r),
            source="merged",
            confidence=0.5,
        )

    @staticmethod
    def _normalize_suggestions(
        llm_suggestions: Mapping[str, Any] | None,
    ) -> Dict[str, bool]:
        if not llm_suggestions:
            return {}

        expected = {
            "reduce_risk",
            "increase_exploration",
            "unblock_ips",
            "spawn_nodes",
            "continue_explorer",
        }
        out: Dict[str, bool] = {}
        for key in expected:
            value = llm_suggestions.get(key, False)
            out[key] = value if isinstance(value, bool) else False
        return out

    @staticmethod
    def _can_spawn_nodes(resources: str) -> bool:
        if psutil is None:
            return False

        try:
            mem = psutil.virtual_memory()
            cpu = float(psutil.cpu_percent(interval=None))
            ram_free_mb = int(mem.available // (1024 * 1024))
            return ram_free_mb >= MIN_FREE_RAM_MB_TO_SPAWN and cpu < CPU_MAX_PERCENT_TO_SPAWN
        except Exception:
            return False