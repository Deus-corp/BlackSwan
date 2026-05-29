from dataclasses import dataclass, field
from typing import Any

from src.swarms.common.protocols.briefs import BriefScope, BriefStatus
from src.swarms.overseer.overseer_core.brief_builder import build_global_swarm_brief


@dataclass
class DummySnapshot:
    swarm_counts: dict[str, int] = field(default_factory=lambda: {"trade": 2, "memory": 1})
    trade_nodes: int = 2
    security_nodes: int = 1
    explorer_nodes: int = 1
    improver_nodes: int = 1
    trade_capital: float = 1000.0
    trade_fitness: float = 0.5


def test_build_global_swarm_brief_for_healthy_state() -> None:
    brief = build_global_swarm_brief(
        snapshot=DummySnapshot(),
        topology_health={
            "trade": {"status": "healthy"},
            "memory": {"status": "healthy"},
        },
        memory_intelligence={
            "aggregate": {
                "status": "healthy",
                "gold_candidates": 0,
                "review_candidates": 0,
                "alert_candidates": 0,
                "dedupe_candidates": 0,
            }
        },
        evidence_ids=["ev-1"],
    )

    assert brief.scope == BriefScope.GLOBAL.value
    assert brief.status == BriefStatus.HEALTHY.value
    assert brief.swarm == "overseer"
    assert brief.key_metrics["swarm_counts"] == {"trade": 2, "memory": 1}
    assert brief.key_metrics["trade_nodes"] == 2
    assert brief.evidence_ids == ["ev-1"]
    assert brief.risks == []
    assert "Global swarm status is healthy" in brief.summary


def test_build_global_swarm_brief_promotes_memory_gold_candidates() -> None:
    brief = build_global_swarm_brief(
        snapshot=DummySnapshot(),
        topology_health={"trade": {"status": "healthy"}},
        memory_intelligence={
            "aggregate": {
                "status": "valuable_activity",
                "gold_candidates": 2,
                "review_candidates": 0,
                "alert_candidates": 0,
                "dedupe_candidates": 0,
            }
        },
    )

    assert brief.status == BriefStatus.HEALTHY.value
    assert brief.key_metrics["memory_gold_candidates"] == 2
    assert brief.opportunities[0]["title"] == "memory gold candidates available"
    assert any(
        item["payload"].get("directive") == "PROMOTE_GOLD_CANDIDATES"
        for item in brief.recommended_actions
    )


def test_build_global_swarm_brief_reports_degraded_swarms_and_memory_alerts() -> None:
    brief = build_global_swarm_brief(
        snapshot=DummySnapshot(),
        topology_health={
            "trade": {"status": "healthy"},
            "memory": {"status": "degraded"},
            "security": "unknown",
        },
        memory_intelligence={
            "aggregate": {
                "status": "healthy",
                "gold_candidates": 0,
                "review_candidates": 1,
                "alert_candidates": 3,
                "dedupe_candidates": 2,
            }
        },
    )

    assert brief.status == BriefStatus.DEGRADED.value
    assert brief.key_metrics["memory_alert_candidates"] == 3
    assert any(item["title"] == "degraded swarms detected" for item in brief.risks)
    assert any(item["title"] == "memory alert candidates detected" for item in brief.risks)
    assert any(item["title"] == "review memory candidates" for item in brief.recommended_actions)
    assert "Degraded swarms" in brief.summary