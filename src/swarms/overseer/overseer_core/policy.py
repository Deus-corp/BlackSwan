"""Deterministic policy engine for overseer decisions.

PolicyEngine is the safety-first merge layer between:
- hard deterministic rules
- soft LLM suggestions

Important:
    LLM suggestions can only add advisory or non-critical recommendations.
    They cannot disable hard safety constraints.

Improver integration v2:
    Improver-related flags are advisory-only for now:
    - run_improver_once
    - pause_improver

    ActionExecutor intentionally does not execute them yet.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

try:
    import psutil
except ImportError:
    psutil = None

from src.swarms.overseer.overseer_core.models import OverseerDecision, SwarmSnapshot

logger = logging.getLogger(__name__)

# Hard safety thresholds
TRADE_DQ_HIGH_THRESHOLD: Final[float] = 0.25
TRADE_CAPITAL_LOW_THRESHOLD: Final[float] = 2000.0
BLOCKED_IPS_HIGH_THRESHOLD: Final[int] = 50
EXPLORE_FINDINGS_STOP_THRESHOLD: Final[int] = 100

# Resource thresholds for advisory spawn decisions
MIN_FREE_RAM_MB_TO_SPAWN: Final[int] = 500
CPU_MAX_PERCENT_TO_SPAWN: Final[float] = 85.0

# Improver advisory thresholds
IMPROVER_FAILED_HIGH_THRESHOLD: Final[int] = 5
IMPROVER_QUARANTINED_HIGH_THRESHOLD: Final[int] = 20
IMPROVER_ERROR_HIGH_THRESHOLD: Final[int] = 1
IMPROVER_LONG_CYCLE_SECONDS: Final[float] = 1800.0

LLM_ALLOWED_KEYS: Final[set[str]] = {
    "reduce_risk",
    "increase_exploration",
    "unblock_ips",
    "spawn_nodes",
    "continue_explorer",
    "run_improver_once",
    "pause_improver",
}


class PolicyEngine:
    """Applies hard rules and merges them with soft LLM suggestions."""

    def evaluate_hard_rules(self, snapshot: SwarmSnapshot) -> OverseerDecision:
        """Evaluate deterministic safety and operational constraints."""
        reasons: list[str] = []

        reduce_risk = False
        unblock_ips = False
        continue_explorer = True

        # Advisory-only improver flags.
        run_improver_once = False
        pause_improver = False

        if snapshot.trade_dq > TRADE_DQ_HIGH_THRESHOLD:
            reduce_risk = True
            reasons.append(
                f"trade_dq={snapshot.trade_dq:.4f} > {TRADE_DQ_HIGH_THRESHOLD:.4f}"
            )

        if snapshot.trade_capital < TRADE_CAPITAL_LOW_THRESHOLD:
            reduce_risk = True
            reasons.append(
                f"trade_capital={snapshot.trade_capital:.2f} < {TRADE_CAPITAL_LOW_THRESHOLD:.2f}"
            )

        if snapshot.recent_vulnerability_alerts > 0:
            reduce_risk = True
            reasons.append(
                f"vulnerabilities={snapshot.recent_vulnerability_alerts} > 0"
            )

        if snapshot.blocked_ips > BLOCKED_IPS_HIGH_THRESHOLD:
            unblock_ips = True
            reasons.append(
                f"blocked_ips={snapshot.blocked_ips} > {BLOCKED_IPS_HIGH_THRESHOLD}"
            )

        if snapshot.recent_findings > EXPLORE_FINDINGS_STOP_THRESHOLD:
            continue_explorer = False
            reasons.append(
                f"findings={snapshot.recent_findings} > {EXPLORE_FINDINGS_STOP_THRESHOLD}"
            )

        # Improver advisory safety:
        # If improver is failing/quarantining too much, policy recommends pause,
        # but executor will not apply this automatically yet.
        if snapshot.improver_files_failed > IMPROVER_FAILED_HIGH_THRESHOLD:
            pause_improver = True
            reasons.append(
                f"improver_failed={snapshot.improver_files_failed} > {IMPROVER_FAILED_HIGH_THRESHOLD}"
            )

        if snapshot.improver_files_quarantined > IMPROVER_QUARANTINED_HIGH_THRESHOLD:
            pause_improver = True
            reasons.append(
                f"improver_quarantined={snapshot.improver_files_quarantined} > {IMPROVER_QUARANTINED_HIGH_THRESHOLD}"
            )

        if snapshot.improver_last_error_count >= IMPROVER_ERROR_HIGH_THRESHOLD:
            pause_improver = True
            reasons.append(
                f"improver_errors={snapshot.improver_last_error_count} >= {IMPROVER_ERROR_HIGH_THRESHOLD}"
            )

        if snapshot.improver_last_cycle_duration_seconds > IMPROVER_LONG_CYCLE_SECONDS:
            pause_improver = True
            reasons.append(
                f"improver_cycle_duration={snapshot.improver_last_cycle_duration_seconds:.1f}s > {IMPROVER_LONG_CYCLE_SECONDS:.1f}s"
            )

        # Advisory run signal:
        # This stays conservative. We only mark it if improver is visible,
        # healthy enough, and has not produced useful improvements yet.
        if (
            snapshot.improver_nodes > 0
            and snapshot.improver_files_processed == 0
            and snapshot.improver_last_error_count == 0
            and not pause_improver
        ):
            run_improver_once = True
            reasons.append("improver_idle_advisory_run_once")

        spawn_nodes_advisory = self._can_spawn_nodes(snapshot)
        reasons.append(
            "resource_check_allows_spawn"
            if spawn_nodes_advisory
            else "resource_check_blocks_spawn"
        )

        if not reasons:
            reasons.append("hard_rules_nominal")

        return OverseerDecision(
            reduce_risk=reduce_risk,
            increase_exploration=False,
            unblock_ips=unblock_ips,
            spawn_nodes=spawn_nodes_advisory,
            continue_explorer=continue_explorer,
            run_improver_once=run_improver_once,
            pause_improver=pause_improver,
            reason="; ".join(reasons),
            source="hard",
            confidence=1.0,
        )

    def merge(
        self,
        hard_rules: OverseerDecision,
        llm_suggestions: Mapping[str, Any] | None,
    ) -> OverseerDecision:
        """Merge hard rules with LLM suggestions using safety-first semantics.

        Hard rules are authoritative:
        - LLM cannot disable reduce_risk if hard rule enabled it.
        - LLM cannot force continue_explorer if hard rule pauses it.
        - LLM cannot spawn nodes unless resources allow.
        - LLM cannot increase exploration during active risk reduction.

        Improver semantics:
        - pause_improver is safety/advisory. Hard pause recommendation wins.
        - run_improver_once is advisory and blocked if pause_improver is active.
        - neither flag is executed by ActionExecutor yet.
        """
        suggestions = self._normalize_suggestions(llm_suggestions)

        if not suggestions:
            return OverseerDecision(
                reduce_risk=hard_rules.reduce_risk,
                increase_exploration=hard_rules.increase_exploration,
                unblock_ips=hard_rules.unblock_ips,
                spawn_nodes=hard_rules.spawn_nodes,
                continue_explorer=hard_rules.continue_explorer,
                run_improver_once=hard_rules.run_improver_once,
                pause_improver=hard_rules.pause_improver,
                reason=hard_rules.reason,
                source="hard",
                confidence=hard_rules.confidence,
            )

        reduce_risk = hard_rules.reduce_risk or suggestions.get("reduce_risk", False)

        increase_exploration = (
            suggestions.get("increase_exploration", False)
            and not reduce_risk
            and hard_rules.continue_explorer
        )

        # Hard unblock_ips remains authoritative. LLM cannot trigger UNBLOCK_ALL alone.
        unblock_ips = hard_rules.unblock_ips

        # spawn_nodes remains advisory-only.
        spawn_nodes = hard_rules.spawn_nodes and suggestions.get("spawn_nodes", False)

        continue_explorer = hard_rules.continue_explorer and suggestions.get(
            "continue_explorer",
            True,
        )

        # Improver advisory merge:
        # pause wins over run.
        pause_improver = hard_rules.pause_improver or suggestions.get("pause_improver", False)

        run_improver_once = (
            (hard_rules.run_improver_once or suggestions.get("run_improver_once", False))
            and not pause_improver
        )

        reason = self._merge_reasons(
            hard_reason=hard_rules.reason,
            suggestions=suggestions,
            advisory_spawn_nodes=spawn_nodes,
            run_improver_once=run_improver_once,
            pause_improver=pause_improver,
        )

        confidence = self._merged_confidence(
            hard_rules=hard_rules,
            suggestions=suggestions,
            reduce_risk=reduce_risk,
            pause_improver=pause_improver,
        )

        return OverseerDecision(
            reduce_risk=reduce_risk,
            increase_exploration=increase_exploration,
            unblock_ips=unblock_ips,
            spawn_nodes=spawn_nodes,
            continue_explorer=continue_explorer,
            run_improver_once=run_improver_once,
            pause_improver=pause_improver,
            reason=reason,
            source="merged",
            confidence=confidence,
        )

    @staticmethod
    def _normalize_suggestions(
        llm_suggestions: Mapping[str, Any] | None,
    ) -> dict[str, bool]:
        """Sanitize LLM suggestions into allowed boolean flags."""
        if not llm_suggestions:
            return {}

        normalized: dict[str, bool] = {}

        for key in LLM_ALLOWED_KEYS:
            normalized[key] = PolicyEngine._to_bool(
                llm_suggestions.get(key),
                default=(key == "continue_explorer"),
            )

        return normalized

    @staticmethod
    def _to_bool(value: Any, *, default: bool = False) -> bool:
        """Convert loose LLM values into bool safely."""
        if isinstance(value, bool):
            return value

        if value is None:
            return default

        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
                return True
            if cleaned in {"0", "false", "no", "n", "off", "disable", "disabled"}:
                return False

        return default

    @staticmethod
    def _merge_reasons(
        *,
        hard_reason: str,
        suggestions: Mapping[str, bool],
        advisory_spawn_nodes: bool,
        run_improver_once: bool,
        pause_improver: bool,
    ) -> str:
        """Build compact explainable reason string."""
        parts = [hard_reason or "hard_rules_nominal"]

        enabled_llm_flags = [
            key
            for key, enabled in suggestions.items()
            if enabled
        ]

        if enabled_llm_flags:
            parts.append(f"llm_enabled={','.join(sorted(enabled_llm_flags))}")

        if suggestions.get("spawn_nodes") and not advisory_spawn_nodes:
            parts.append("spawn_nodes_advisory_only_or_blocked")

        if run_improver_once:
            parts.append("run_improver_once_advisory_only")

        if pause_improver:
            parts.append("pause_improver_advisory_only")

        return " | ".join(parts)

    @staticmethod
    def _merged_confidence(
        *,
        hard_rules: OverseerDecision,
        suggestions: Mapping[str, bool],
        reduce_risk: bool,
        pause_improver: bool,
    ) -> float:
        """Compute conservative merged confidence."""
        if reduce_risk:
            return 0.95

        if pause_improver:
            return 0.9

        if any(suggestions.values()):
            return 0.75

        return min(1.0, max(0.0, hard_rules.confidence))

    @staticmethod
    def _can_spawn_nodes(snapshot: SwarmSnapshot) -> bool:
        """Check system resources for advisory spawn capability.

        This is advisory because actual spawning is not implemented in
        ActionExecutor yet.
        """
        if psutil is None:
            return False

        try:
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)

            ram_free_mb = int(mem.available // (1024 * 1024))

            enough_ram = ram_free_mb >= MIN_FREE_RAM_MB_TO_SPAWN
            enough_cpu = float(cpu) < CPU_MAX_PERCENT_TO_SPAWN
            not_in_risk = snapshot.trade_dq <= TRADE_DQ_HIGH_THRESHOLD

            return enough_ram and enough_cpu and not_in_risk

        except (RuntimeError, PermissionError, ValueError, OSError) as exc:
            logger.warning("Resource check failed: %s", exc)
            return False