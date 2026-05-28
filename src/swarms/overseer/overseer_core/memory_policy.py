"""Policy mapping from memory intelligence to Overseer directives."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class MemoryDirectiveAction(str, Enum):
    """Actions Overseer may take based on memory intelligence."""

    OBSERVE = "observe"
    PROMOTE_GOLD = "promote_gold"
    REVIEW_MEMORY = "review_memory"
    REDUCE_RISK = "reduce_risk"
    RESTORE_MEMORY = "restore_memory"


class MemoryDirectiveSeverity(str, Enum):
    """Directive severity."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class MemoryDirective:
    """Overseer directive derived from memory intelligence."""

    action: MemoryDirectiveAction
    severity: MemoryDirectiveSeverity
    reason: str
    status: str = "unknown"
    gold_candidates: int = 0
    review_candidates: int = 0
    alert_candidates: int = 0
    dedupe_candidates: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        data["severity"] = self.severity.value
        return data


def decide_memory_directive(memory_aggregate: dict[str, Any]) -> MemoryDirective:
    """Map memory intelligence aggregate to a lightweight Overseer directive."""
    if not isinstance(memory_aggregate, dict):
        return MemoryDirective(
            action=MemoryDirectiveAction.RESTORE_MEMORY,
            severity=MemoryDirectiveSeverity.WARNING,
            reason="invalid_memory_intelligence",
        )

    status = str(memory_aggregate.get("status") or "unknown")
    gold = _safe_int(memory_aggregate.get("gold_candidates", 0))
    review = _safe_int(memory_aggregate.get("review_candidates", 0))
    alert = _safe_int(memory_aggregate.get("alert_candidates", 0))
    dedupe = _safe_int(memory_aggregate.get("dedupe_candidates", 0))

    if status == "degraded":
        return MemoryDirective(
            action=MemoryDirectiveAction.RESTORE_MEMORY,
            severity=MemoryDirectiveSeverity.CRITICAL,
            reason="memory_degraded",
            status=status,
            gold_candidates=gold,
            review_candidates=review,
            alert_candidates=alert,
            dedupe_candidates=dedupe,
        )

    if status == "danger_detected" or alert > 0:
        return MemoryDirective(
            action=MemoryDirectiveAction.REDUCE_RISK,
            severity=MemoryDirectiveSeverity.CRITICAL,
            reason="memory_alert_candidates_detected",
            status=status,
            gold_candidates=gold,
            review_candidates=review,
            alert_candidates=alert,
            dedupe_candidates=dedupe,
        )

    if status == "needs_review" or review > 0:
        return MemoryDirective(
            action=MemoryDirectiveAction.REVIEW_MEMORY,
            severity=MemoryDirectiveSeverity.WARNING,
            reason="memory_review_candidates_detected",
            status=status,
            gold_candidates=gold,
            review_candidates=review,
            alert_candidates=alert,
            dedupe_candidates=dedupe,
        )

    if status == "valuable_activity" or gold > 0:
        return MemoryDirective(
            action=MemoryDirectiveAction.PROMOTE_GOLD,
            severity=MemoryDirectiveSeverity.INFO,
            reason="memory_gold_candidates_detected",
            status=status,
            gold_candidates=gold,
            review_candidates=review,
            alert_candidates=alert,
            dedupe_candidates=dedupe,
        )

    return MemoryDirective(
        action=MemoryDirectiveAction.OBSERVE,
        severity=MemoryDirectiveSeverity.INFO,
        reason="memory_nominal",
        status=status,
        gold_candidates=gold,
        review_candidates=review,
        alert_candidates=alert,
        dedupe_candidates=dedupe,
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default