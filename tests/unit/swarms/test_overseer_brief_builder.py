from dataclasses import dataclass, field

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

def test_build_global_swarm_brief_reports_runtime_evidence_opportunity() -> None:
    snapshot = {
        "active_swarm_counts": {"memory": 1, "overseer": 1},
        "memory_intelligence": {
            "aggregate": {
                "status": "valuable_activity",
                "gold_candidates": 0,
                "runtime_evidence_records": 1,
                "runtime_evidence_gold_candidates": 1,
                "runtime_evidence_review_candidates": 0,
                "runtime_evidence_alert_candidates": 0,
            }
        },
    }

    brief = build_global_swarm_brief(
        snapshot=snapshot,
        memory_intelligence=snapshot["memory_intelligence"],
    )

    assert brief.key_metrics["memory_runtime_evidence_records"] == 1
    assert brief.key_metrics["memory_runtime_evidence_gold_candidates"] == 1
    assert any("Runtime evidence" in item.get("title", "") for item in brief.opportunities)
    assert any(
        "runtime evidence" in item.get("detail", "").lower()
        for item in brief.recommended_actions
    )
    assert "verified runtime evidence" in brief.summary.lower()


def test_build_global_swarm_brief_reports_runtime_evidence_alert_risk() -> None:
    snapshot = {
        "active_swarm_counts": {"memory": 1, "overseer": 1},
        "memory_intelligence": {
            "aggregate": {
                "status": "danger_detected",
                "gold_candidates": 0,
                "runtime_evidence_records": 1,
                "runtime_evidence_gold_candidates": 0,
                "runtime_evidence_review_candidates": 0,
                "runtime_evidence_alert_candidates": 1,
            }
        },
    }

    brief = build_global_swarm_brief(
        snapshot=snapshot,
        memory_intelligence=snapshot["memory_intelligence"],
    )

    assert brief.status == "degraded"
    assert brief.key_metrics["memory_runtime_evidence_alert_candidates"] == 1
    assert any("Runtime evidence alerts" in item.get("title", "") for item in brief.risks)
    assert any(
        "review" in item.get("title", "").lower()
        for item in brief.recommended_actions
    )
    assert "runtime evidence alert" in brief.summary.lower()

def test_build_global_swarm_brief_reports_security_validation_critical_risk() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 2,
            "security_validation_invalid_records": 1,
            "security_validation_critical_records": 1,
        },
    )

    assert brief.status == "critical"
    assert brief.key_metrics["security_validation_records"] == 2
    assert brief.key_metrics["security_validation_invalid_records"] == 1
    assert brief.key_metrics["security_validation_critical_records"] == 1
    assert any("Critical security validation" in item.get("title", "") for item in brief.risks)
    assert any("Review security validation" in item.get("title", "") for item in brief.recommended_actions)
    assert "critical validation failure" in brief.summary.lower()


def test_build_global_swarm_brief_reports_security_validation_warning_risk() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 2,
            "security_validation_invalid_records": 1,
            "security_validation_critical_records": 0,
        },
    )

    assert brief.status == "healthy"
    assert brief.key_metrics["security_validation_invalid_records"] == 1
    assert any("Security validation warnings" in item.get("title", "") for item in brief.risks)
    assert "validation warning" in brief.summary.lower()


def test_build_global_swarm_brief_extracts_security_validation_from_snapshot_heartbeats() -> None:
    snapshot = {
        "active_swarm_counts": {"security": 1, "overseer": 1},
        "latest_swarm_heartbeats": {
            "security": [
                {
                    "type": "swarm_heartbeat",
                    "swarm": "security",
                    "node_id": "security-1",
                    "metrics": {
                        "security_validation_records": 2,
                        "security_validation_valid_records": 1,
                        "security_validation_invalid_records": 1,
                        "security_validation_critical_records": 1,
                        "security_validation_invalid_reasons": {
                            "unsafe_or_unknown_action": 1,
                        },
                        "security_validation_record_type_counts": {
                            "replay_evidence_lifecycle_result": 1,
                        },
                        "security_validation_warning_reasons": {
                            "execution_not_observed_before_timeout": 1,
                        },
                        "simulation_replay_executions": 1,
                        "simulation_replay_execution_completed": 1,
                        "simulation_replay_execution_failed": 0,
                        "simulation_replay_execution_status_counts": {"completed": 1},
                    },
                }
            ]
        },
    }

    brief = build_global_swarm_brief(snapshot=snapshot)

    assert brief.status == "critical"
    assert brief.key_metrics["security_validation_records"] == 2
    assert brief.key_metrics["security_validation_invalid_records"] == 1
    assert brief.key_metrics["security_validation_critical_records"] == 1
    assert any("Critical security validation" in item.get("title", "") for item in brief.risks)
    assert brief.key_metrics["simulation_replay_executions"] == 1
    assert brief.key_metrics["simulation_replay_execution_completed"] == 1
    assert brief.key_metrics["security_replay_lifecycle_results"] == 1
    assert brief.key_metrics["security_replay_lifecycle_timeouts"] == 1

def test_build_global_swarm_brief_reports_simulation_replay_opportunity() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"simulation": 1, "overseer": 1}},
        simulation_replay={
            "simulation_replay_scenarios": 1,
            "simulation_replay_pending": 1,
            "simulation_replay_completed": 0,
            "simulation_replay_failed": 0,
        },
    )

    assert brief.key_metrics["simulation_replay_scenarios"] == 1
    assert brief.key_metrics["simulation_replay_pending"] == 1
    assert any("Simulation replay" in item.get("title", "") for item in brief.opportunities)
    assert any("simulation replay" in item.get("detail", "").lower() for item in brief.recommended_actions)
    assert "pending replay" in brief.summary.lower()


def test_build_global_swarm_brief_reports_simulation_replay_failure_risk() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"simulation": 1, "overseer": 1}},
        simulation_replay={
            "simulation_replay_scenarios": 1,
            "simulation_replay_pending": 0,
            "simulation_replay_completed": 0,
            "simulation_replay_failed": 1,
        },
    )

    assert brief.key_metrics["simulation_replay_failed"] == 1
    assert any("Simulation replay failures" in item.get("title", "") for item in brief.risks)
    assert "failed replay" in brief.summary.lower()


def test_build_global_swarm_brief_extracts_simulation_replay_from_snapshot_heartbeats() -> None:
    snapshot = {
        "active_swarm_counts": {"simulation": 1, "overseer": 1},
        "latest_swarm_heartbeats": {
            "simulation": [
                {
                    "type": "swarm_heartbeat",
                    "swarm": "simulation",
                    "node_id": "simulation-1",
                    "metrics": {
                        "simulation_replay_scenarios": 1,
                        "simulation_replay_pending": 1,
                        "simulation_replay_completed": 0,
                        "simulation_replay_failed": 0,
                    },
                }
            ]
        },
    }

    brief = build_global_swarm_brief(snapshot=snapshot)

    assert brief.key_metrics["simulation_replay_scenarios"] == 1
    assert brief.key_metrics["simulation_replay_pending"] == 1
    assert any("Simulation replay" in item.get("title", "") for item in brief.opportunities)

def test_build_global_swarm_brief_reports_simulation_replay_execution_opportunity() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"simulation": 1, "overseer": 1}},
        simulation_replay={
            "simulation_replay_scenarios": 1,
            "simulation_replay_pending": 0,
            "simulation_replay_completed": 0,
            "simulation_replay_failed": 0,
            "simulation_replay_executions": 1,
            "simulation_replay_execution_completed": 1,
            "simulation_replay_execution_failed": 0,
        },
    )

    assert brief.key_metrics["simulation_replay_executions"] == 1
    assert brief.key_metrics["simulation_replay_execution_completed"] == 1
    assert any(
        "Simulation replay dry-runs completed" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "completed 1 replay dry-run" in brief.summary.lower()


def test_build_global_swarm_brief_reports_simulation_replay_execution_failure_risk() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"simulation": 1, "overseer": 1}},
        simulation_replay={
            "simulation_replay_scenarios": 1,
            "simulation_replay_pending": 0,
            "simulation_replay_completed": 0,
            "simulation_replay_failed": 0,
            "simulation_replay_executions": 1,
            "simulation_replay_execution_completed": 0,
            "simulation_replay_execution_failed": 1,
        },
    )

    assert brief.key_metrics["simulation_replay_execution_failed"] == 1
    assert any(
        "Simulation replay dry-run failures" in item.get("title", "")
        for item in brief.risks
    )
    assert "failed replay dry-run" in brief.summary.lower()

def test_build_global_swarm_brief_reports_memory_replay_execution_evidence() -> None:
    memory_intelligence = {
        "aggregate": {
            "status": "valuable_activity",
            "replay_execution_evidence_records": 1,
            "replay_execution_evidence_passed": 1,
            "replay_execution_evidence_failed": 0,
        },
        "nodes": [],
    }

    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"memory": 1, "overseer": 1}},
        memory_intelligence=memory_intelligence,
    )

    assert brief.key_metrics["memory_replay_execution_evidence_records"] == 1
    assert brief.key_metrics["memory_replay_execution_evidence_passed"] == 1
    assert any(
        "Replay execution evidence" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay execution evidence" in brief.summary.lower()


def test_build_global_swarm_brief_reports_replay_lifecycle_security_validation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_evidence_lifecycle_result": 1,
            },
        },
    )

    assert brief.key_metrics["security_replay_lifecycle_results"] == 1
    assert any(
        "Replay evidence lifecycle validation" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay evidence lifecycle result" in brief.summary.lower()

def test_build_global_swarm_brief_reports_replay_lifecycle_timeout_warnings() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_warning_reasons": {
                "execution_not_observed_before_timeout": 1,
            },
        },
    )

    assert brief.key_metrics["security_replay_lifecycle_timeouts"] == 1
    assert any(
        "Replay lifecycle timeout warnings" in item.get("title", "")
        for item in brief.risks
    )

    retry_actions = [
        item
        for item in brief.recommended_actions
        if item.get("payload", {}).get("recommendation") == "retry_replay_lifecycle_check"
    ]

    assert retry_actions
    assert retry_actions[0]["payload"]["timeout_profile"] == "standard"
    assert retry_actions[0]["payload"]["suggested_wait_seconds"] == 15.0
    assert retry_actions[0]["payload"]["suggested_poll_interval"] == 0.5

    assert "replay lifecycle timeout warning" in brief.summary.lower()