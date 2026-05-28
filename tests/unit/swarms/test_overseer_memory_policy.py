from src.swarms.overseer.overseer_core.memory_policy import (
    MemoryDirectiveAction,
    MemoryDirectiveSeverity,
    decide_memory_directive,
)


def test_memory_policy_promotes_gold_candidates() -> None:
    directive = decide_memory_directive(
        {
            "status": "valuable_activity",
            "gold_candidates": 3,
            "review_candidates": 0,
            "alert_candidates": 0,
            "dedupe_candidates": 0,
        }
    )

    assert directive.action == MemoryDirectiveAction.PROMOTE_GOLD
    assert directive.severity == MemoryDirectiveSeverity.INFO
    assert directive.gold_candidates == 3


def test_memory_policy_reduces_risk_on_alerts() -> None:
    directive = decide_memory_directive(
        {
            "status": "danger_detected",
            "gold_candidates": 1,
            "alert_candidates": 1,
        }
    )

    assert directive.action == MemoryDirectiveAction.REDUCE_RISK
    assert directive.severity == MemoryDirectiveSeverity.CRITICAL


def test_memory_policy_restores_degraded_memory() -> None:
    directive = decide_memory_directive(
        {
            "status": "degraded",
            "gold_candidates": 0,
        }
    )

    assert directive.action == MemoryDirectiveAction.RESTORE_MEMORY
    assert directive.severity == MemoryDirectiveSeverity.CRITICAL


def test_memory_policy_observes_nominal_memory() -> None:
    directive = decide_memory_directive(
        {
            "status": "healthy",
            "gold_candidates": 0,
            "review_candidates": 0,
            "alert_candidates": 0,
        }
    )

    assert directive.action == MemoryDirectiveAction.OBSERVE
    assert directive.severity == MemoryDirectiveSeverity.INFO

def test_memory_policy_directive_serializes_to_dict() -> None:
    directive = decide_memory_directive(
        {
            "status": "valuable_activity",
            "gold_candidates": 2,
        }
    )

    data = directive.to_dict()

    assert data["action"] == "promote_gold"
    assert data["severity"] == "info"
    assert data["gold_candidates"] == 2