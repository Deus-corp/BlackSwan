from dataclasses import dataclass, field

from src.swarms.common.protocols.briefs import BriefScope, BriefStatus
from src.swarms.overseer.overseer_core.brief_builder import (
    build_global_swarm_brief,
)


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
                            "replay_lifecycle_retry_rendered_command_result": 1,
                            "replay_lifecycle_retry_execution_eligibility": 1,
                        },
                        "security_validation_warning_reasons": {
                            "execution_not_observed_before_timeout": 1,
                        },
                        "security_validation_retry_approval_decision_modes": {
                            "manual": 1,
                            "policy": 1,
                        },
                        "security_validation_retry_rendered_command_result_statuses": {"skipped": 1},
                        "security_validation_retry_rendered_command_result_reasons": {"execution_disabled": 1},
                        "security_validation_retry_execution_eligibility_statuses": {"blocked": 1},
                        "security_validation_retry_execution_eligibility_reasons": {"execution_disabled": 1},
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
    assert brief.key_metrics["security_retry_manual_approvals"] == 1
    assert brief.key_metrics["security_retry_policy_approvals"] == 1
    assert brief.key_metrics["security_retry_rendered_command_results"] == 1
    assert brief.key_metrics["security_retry_rendered_command_skipped"] == 1
    assert brief.key_metrics["security_retry_execution_eligibilities"] == 1
    assert brief.key_metrics["security_retry_execution_blocked"] == 1

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

    command_template = retry_actions[0]["payload"]["command_template"]

    assert "--timeout-profile standard" in command_template
    assert "<scenario_id>" in command_template
    assert "<new_directive_id>" in command_template
    assert "python -m src.testing.run_replay_evidence_check" in command_template

    assert "replay lifecycle timeout warning" in brief.summary.lower()


def test_build_global_swarm_brief_reports_retry_proposals_from_security_validation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_proposal": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_proposals"] == 1
    assert any(
        "Pending replay lifecycle retry proposals" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "pending replay lifecycle retry proposal" in brief.summary.lower()


def test_build_global_swarm_brief_reports_retry_approvals_from_security_validation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_approval": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_approvals"] == 1
    assert any(
        "Replay lifecycle retry approvals" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay lifecycle retry approval" in brief.summary.lower()


def test_build_global_swarm_brief_reports_retry_approval_decision_modes() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 2,
            "security_validation_valid_records": 2,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_approval": 2,
            },
            "security_validation_retry_approval_decision_modes": {
                "manual": 1,
                "policy": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_approvals"] == 2
    assert brief.key_metrics["security_retry_approval_decision_modes"] == {
        "manual": 1,
        "policy": 1,
    }
    assert brief.key_metrics["security_retry_manual_approvals"] == 1
    assert brief.key_metrics["security_retry_policy_approvals"] == 1
    assert any(
        item.get("payload", {}).get("recommendation")
        == "review_replay_retry_approval_decision_modes"
        for item in brief.opportunities
    )
    assert "manual=1" in brief.summary
    assert "policy=1" in brief.summary


def test_build_global_swarm_brief_reports_retry_execution_plans_from_security_validation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_execution_plan": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_execution_plans"] == 1
    assert any(
        "Replay lifecycle retry execution plans" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay lifecycle retry execution plan" in brief.summary.lower()


def test_build_global_swarm_brief_reports_retry_execution_results_from_security_validation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_execution_result": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_execution_results"] == 1
    assert any(
        "Replay lifecycle retry execution results" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay lifecycle retry execution result" in brief.summary.lower()


def test_build_global_swarm_brief_reports_retry_execution_result_statuses() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 2,
            "security_validation_valid_records": 2,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_execution_result": 2,
            },
            "security_validation_retry_execution_result_statuses": {
                "skipped": 1,
                "rejected": 1,
            },
            "security_validation_retry_execution_result_reasons": {
                "execution_disabled": 1,
                "execution_not_supported": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_execution_results"] == 2
    assert brief.key_metrics["security_retry_execution_skipped"] == 1
    assert brief.key_metrics["security_retry_execution_rejected"] == 1
    assert brief.key_metrics["security_retry_execution_result_statuses"] == {
        "skipped": 1,
        "rejected": 1,
    }
    assert brief.key_metrics["security_retry_execution_result_reasons"] == {
        "execution_disabled": 1,
        "execution_not_supported": 1,
    }
    assert "skipped=1" in brief.summary
    assert "rejected=1" in brief.summary


def test_build_global_swarm_brief_reports_retry_rendered_commands_from_security_validation() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_rendered_command": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_rendered_commands"] == 1
    assert any(
        "Replay lifecycle retry rendered commands" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay lifecycle retry rendered command" in brief.summary.lower()


def test_build_global_swarm_brief_reports_retry_rendered_command_profiles() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 2,
            "security_validation_valid_records": 2,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_rendered_command": 2,
            },
            "security_validation_retry_rendered_command_profiles": {
                "standard": 1,
                "patient": 1,
            },
            "security_validation_retry_rendered_command_decision_modes": {
                "manual": 1,
                "policy": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_rendered_commands"] == 2
    assert brief.key_metrics["security_retry_rendered_command_profiles"] == {
        "standard": 1,
        "patient": 1,
    }
    assert brief.key_metrics["security_retry_rendered_command_decision_modes"] == {
        "manual": 1,
        "policy": 1,
    }
    assert brief.key_metrics["security_retry_rendered_standard_commands"] == 1
    assert brief.key_metrics["security_retry_rendered_patient_commands"] == 1
    assert "standard=1" in brief.summary
    assert "patient=1" in brief.summary


def test_build_global_swarm_brief_reports_retry_rendered_command_results() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_rendered_command_result": 1,
            },
            "security_validation_retry_rendered_command_result_statuses": {
                "skipped": 1,
            },
            "security_validation_retry_rendered_command_result_reasons": {
                "execution_disabled": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_rendered_command_results"] == 1
    assert brief.key_metrics["security_retry_rendered_command_skipped"] == 1
    assert brief.key_metrics["security_retry_rendered_command_rejected"] == 0
    assert brief.key_metrics["security_retry_rendered_command_result_statuses"] == {
        "skipped": 1,
    }
    assert brief.key_metrics["security_retry_rendered_command_result_reasons"] == {
        "execution_disabled": 1,
    }
    assert any(
        "Replay lifecycle retry rendered command results" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "replay lifecycle retry rendered command result" in brief.summary.lower()
    assert "skipped=1" in brief.summary
    assert "rejected=0" in brief.summary


def test_build_global_swarm_brief_reports_retry_execution_eligibility() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_valid_records": 1,
            "security_validation_invalid_records": 0,
            "security_validation_critical_records": 0,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_execution_eligibility": 1,
            },
            "security_validation_retry_execution_eligibility_statuses": {
                "blocked": 1,
            },
            "security_validation_retry_execution_eligibility_reasons": {
                "execution_disabled": 1,
            },
        },
    )

    assert brief.key_metrics["security_retry_execution_eligibilities"] == 1
    assert brief.key_metrics["security_retry_execution_blocked"] == 1
    assert brief.key_metrics["security_retry_execution_eligibility_statuses"] == {
        "blocked": 1,
    }
    assert brief.key_metrics["security_retry_execution_eligibility_reasons"] == {
        "execution_disabled": 1,
    }
    assert any(
        "Replay retry execution eligibility" in item.get("title", "")
        for item in brief.opportunities
    )
    assert "retry execution eligibility record" in brief.summary.lower()
    assert "blocked=1" in brief.summary
    assert "execution_disabled=1" in brief.summary


def test_global_brief_surfaces_controlled_retry_execution_results() -> None:
    brief = build_global_swarm_brief(
        snapshot={"swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_record_type_counts": {
                "replay_lifecycle_retry_controlled_execution_result": 1,
            },
            "security_validation_controlled_execution_result_statuses": {
                "rejected": 1,
            },
            "security_validation_controlled_execution_result_reasons": {
                "controlled_execution_not_implemented": 1,
            },
            "security_validation_controlled_execution_command_parse_valid": {
                "true": 1
            },
            "security_validation_controlled_execution_command_parse_allowlist_matched": {
                "true": 1
            },
            "security_validation_controlled_execution_command_parse_execution_performed": {
                "false": 1
            },
            "security_validation_controlled_execution_operator_authorized": {
                "true": 1,
            },
            "security_validation_controlled_execution_gate_statuses": {
                "blocked": 1,
            },
            "security_validation_controlled_execution_gate_would_execute": {
                "false": 1,
            },
            "security_validation_controlled_execution_gate_would_execute_if_enabled": {
                "false": 1,
            },
            "security_validation_controlled_execution_gate_execution_performed": {
                "false": 1,
            },
            "security_validation_controlled_execution_gate_reasons": {
                "controlled_execution_not_enabled": 1,
                "controlled_execution_implementation_not_enabled": 1,
            },
            "security_validation_controlled_execution_mock_statuses": {
                "mock_executed": 1,
            },
            "security_validation_controlled_execution_mock_performed": {
                "true": 1,
            },
            "security_validation_controlled_execution_mock_subprocess_invoked": {
                "false": 1,
            },
            "security_validation_mock_summary_statuses": {
                "mock_executed": 1,
            },
            "security_validation_mock_summary_performed": {
                "true": 1,
            },
            "security_validation_mock_summary_subprocess_invoked": {
                "false": 1,
            },
            "security_validation_controlled_execution_mock_adapter": {
                "mock": 1,
            },
            "security_validation_controlled_execution_mock_adapter_mode": {
                "mock": 1,
            },
            "security_validation_controlled_execution_mock_adapter_result_statuses": {
                "mock_executed": 1,
            },
            "security_validation_controlled_execution_mock_adapter_subprocess_invoked": {
                "false": 1,
            },
            "security_validation_controlled_execution_mock_adapter_real_execution_enabled": {
                "false": 1,
            },
            "security_validation_controlled_execution_mock_adapter_payload_executed": {
                "false": 1,
            },
            "replay_lifecycle_retry_real_execution_read_only_feedback": 1,
            "real_read_only_feedback_statuses": {"actionable": 1},
            "real_read_only_feedback_source_statuses": {"failed": 1},
            "real_read_only_feedback_source_exit_codes": {"1": 1},
            "real_read_only_feedback_next_actions": {
                "investigate_failed_read_only_evidence_check": 1,
            },
            "real_read_only_feedback_real_execution_enabled": {"false": 1},
            "real_read_only_feedback_execution_performed": {"false": 1},
            "real_read_only_feedback_subprocess_invoked": {"false": 1},
            "real_read_only_feedback_feedback_execution_performed": {"false": 1},
            "real_read_only_feedback_feedback_subprocess_invoked": {"false": 1},
            "replay_lifecycle_retry_real_execution_read_only_repair_plan": 1,
            "real_read_only_repair_plan_statuses": {"planned": 1},
            "real_read_only_repair_plan_source_feedback_statuses": {"actionable": 1},
            "real_read_only_repair_plan_source_statuses": {"failed": 1},
            "real_read_only_repair_plan_source_exit_codes": {"1": 1},
            "real_read_only_repair_plan_next_actions": {
                "review_replay_evidence_repair_plan": 1,
            },
            "real_read_only_repair_plan_item_counts": {"9": 1},
            "real_read_only_repair_plan_requires_operator_review": {"true": 1},
            "real_read_only_repair_plan_repair_execution_enabled": {"false": 1},
            "real_read_only_repair_plan_real_execution_enabled": {"false": 1},
            "real_read_only_repair_plan_subprocess_enabled": {"false": 1},
            "real_read_only_repair_plan_repair_execution_performed": {"false": 1},
            "real_read_only_repair_plan_repair_subprocess_invoked": {"false": 1},
            "real_read_only_repair_plan_execution_performed": {"false": 1},
            "real_read_only_repair_plan_subprocess_invoked": {"false": 1},
            "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle": 1,
            "real_read_only_repair_action_bundle_statuses": {"assembled": 1},
            "real_read_only_repair_action_bundle_source_plan_statuses": {"planned": 1},
            "real_read_only_repair_action_bundle_source_feedback_statuses": {"actionable": 1},
            "real_read_only_repair_action_bundle_source_statuses": {"failed": 1},
            "real_read_only_repair_action_bundle_source_exit_codes": {"1": 1},
            "real_read_only_repair_action_bundle_next_actions": {
                "review_repair_action_bundle": 1,
            },
            "real_read_only_repair_action_bundle_item_counts": {"9": 1},
            "real_read_only_repair_action_bundle_source_item_counts": {"9": 1},
            "real_read_only_repair_action_bundle_requires_operator_review": {"true": 1},
            "real_read_only_repair_action_bundle_reviewed": {"false": 1},
            "real_read_only_repair_action_bundle_bundle_execution_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_repair_execution_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_real_execution_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_subprocess_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_bundle_execution_performed": {"false": 1},
            "real_read_only_repair_action_bundle_bundle_subprocess_invoked": {"false": 1},
            "real_read_only_repair_action_bundle_execution_performed": {"false": 1},
            "real_read_only_repair_action_bundle_subprocess_invoked": {"false": 1},
            "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review": 1,
            "real_read_only_repair_action_bundle_review_statuses": {"approved": 1},
            "real_read_only_repair_action_bundle_review_source_bundle_statuses": {
                "assembled": 1
            },
            "real_read_only_repair_action_bundle_review_next_actions": {
                "prepare_repair_execution_approval_scaffold": 1,
            },
            "real_read_only_repair_action_bundle_review_operator_authorized": {"true": 1},
            "real_read_only_repair_action_bundle_review_reviewed": {"true": 1},
            "real_read_only_repair_action_bundle_review_approved": {"true": 1},
            "real_read_only_repair_action_bundle_review_repair_execution_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_review_real_execution_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_review_subprocess_enabled": {"false": 1},
            "real_read_only_repair_action_bundle_review_execution_performed": {"false": 1},
            "real_read_only_repair_action_bundle_review_subprocess_invoked": {"false": 1},
        },
    )

    text = brief.summary

    assert "Security validated 1 controlled retry execution result record(s)." in text
    assert (
        "Controlled retry execution results: rejected=1, skipped=0, executed=0."
        in text
    )
    assert (
        "Controlled retry execution remains disabled/not implemented: "
        "controlled_execution_not_implemented=1."
        in text
    )
    assert brief.key_metrics["security_controlled_execution_results"] == 1
    assert brief.key_metrics["security_controlled_execution_rejected"] == 1
    assert brief.key_metrics["security_controlled_execution_skipped"] == 0
    assert brief.key_metrics["security_controlled_execution_executed"] == 0
    assert brief.key_metrics["security_controlled_execution_not_implemented"] == 1
    assert brief.key_metrics["security_controlled_command_parse_valid"] == 1
    assert brief.key_metrics["security_controlled_command_parse_allowlisted"] == 1
    assert brief.key_metrics["security_controlled_command_parse_execution_performed"] == 0
    assert (
        "Controlled retry execution operator authorization intent observed: "
        "operator_authorized=1."
        in text
    )
    assert (
        "Controlled retry execution gate is blocked: "
        "controlled_execution_not_enabled=1, "
        "controlled_execution_implementation_not_enabled=1."
        in text
    )
    assert "No controlled command execution was performed." in text
    assert brief.key_metrics["security_controlled_execution_operator_authorized"] == 1
    assert brief.key_metrics["security_controlled_execution_gate_blocked"] == 1
    assert brief.key_metrics["security_controlled_execution_gate_would_execute"] == 0
    assert (
        brief.key_metrics["security_controlled_execution_gate_execution_performed"]
        == 0
    )
    assert (
        "Controlled mock execution observed: "
        "mock_executed=1, mock_performed=1, subprocess_invoked=0. "
        "Real execution remains disabled."
        in text
    )
    assert brief.key_metrics["security_controlled_mock_executed"] == 1
    assert brief.key_metrics["security_controlled_mock_performed"] == 1
    assert brief.key_metrics["security_controlled_mock_subprocess_invoked"] == 0
    assert (
        "Controlled mock execution summary observed: "
        "mock_executed=1, mock_performed=1, subprocess_invoked=0."
        in text
    )
    assert brief.key_metrics["security_mock_summary_executed"] == 1
    assert brief.key_metrics["security_mock_summary_performed"] == 1
    assert brief.key_metrics["security_mock_summary_subprocess_invoked"] == 0
    assert (
        "Controlled mock adapter contract observed: "
        "adapter=mock:1, mode=mock:1, mock_executed=1, "
        "subprocess_invoked=0, real_execution_enabled=0, payload_executed=0."
        in text
    )
    assert brief.key_metrics["security_mock_adapter"] == 1
    assert brief.key_metrics["security_mock_adapter_mode"] == 1
    assert brief.key_metrics["security_mock_adapter_result_status"] == 1
    assert brief.key_metrics["security_mock_adapter_subprocess_invoked"] == 0
    assert brief.key_metrics["security_mock_adapter_real_execution_enabled"] == 0
    assert brief.key_metrics["security_mock_adapter_payload_executed"] == 0
    assert brief.key_metrics["security_read_only_feedback_records"] == 1
    assert brief.key_metrics["security_read_only_feedback_actionable"] == 1
    assert brief.key_metrics["security_read_only_feedback_source_failed"] == 1
    assert brief.key_metrics["security_read_only_feedback_exit_code_1"] == 1
    assert brief.key_metrics["security_read_only_feedback_next_action_investigate"] == 1
    assert brief.key_metrics["security_read_only_feedback_real_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_feedback_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_feedback_subprocess_invoked"] == 0
    assert brief.key_metrics["security_read_only_feedback_feedback_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_feedback_feedback_subprocess_invoked"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_records"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_planned"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_source_actionable"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_source_failed"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_exit_code_1"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_item_count_9"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_next_action_review"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_requires_operator_review"] == 1
    assert brief.key_metrics["security_read_only_repair_plan_repair_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_real_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_subprocess_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_repair_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_repair_subprocess_invoked"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_repair_plan_subprocess_invoked"] == 0

    assert "Read-only repair plan observed" in brief.summary
    assert "records=1" in brief.summary
    assert "planned=1" in brief.summary
    assert "source_actionable=1" in brief.summary
    assert "source_failed=1" in brief.summary
    assert "repair_item_count_9=1" in brief.summary
    assert "next_action=review_replay_evidence_repair_plan" in brief.summary
    assert "repair_execution_enabled=0" in brief.summary
    assert "real_execution_enabled=0" in brief.summary
    assert "subprocess_enabled=0" in brief.summary
    assert "repair_execution_performed=0" in brief.summary
    assert "repair_subprocess_invoked=0" in brief.summary

    assert brief.key_metrics["security_read_only_repair_action_bundle_records"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_assembled"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_source_planned"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_source_actionable"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_source_failed"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_exit_code_1"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_item_count_9"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_source_item_count_9"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_next_action_review"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_requires_operator_review"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_reviewed"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_bundle_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_repair_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_real_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_subprocess_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_bundle_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_bundle_subprocess_invoked"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_subprocess_invoked"] == 0

    assert "Read-only repair action bundle observed" in brief.summary
    assert "records=1" in brief.summary
    assert "assembled=1" in brief.summary
    assert "source_planned=1" in brief.summary
    assert "source_actionable=1" in brief.summary
    assert "source_failed=1" in brief.summary
    assert "bundle_item_count_9=1" in brief.summary
    assert "next_action=review_repair_action_bundle" in brief.summary
    assert "requires_operator_review=1" in brief.summary
    assert "reviewed=0" in brief.summary
    assert "bundle_execution_enabled=0" in brief.summary
    assert "real_execution_enabled=0" in brief.summary
    assert "subprocess_enabled=0" in brief.summary
    assert "bundle_execution_performed=0" in brief.summary
    assert "bundle_subprocess_invoked=0" in brief.summary

    assert brief.key_metrics["security_read_only_repair_action_bundle_review_records"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_approved"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_source_assembled"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_next_action_prepare"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_operator_authorized"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_reviewed"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_approved_flag"] == 1
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_repair_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_real_execution_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_subprocess_enabled"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_execution_performed"] == 0
    assert brief.key_metrics["security_read_only_repair_action_bundle_review_subprocess_invoked"] == 0

    assert "Repair action bundle review observed" in brief.summary
    assert "approved=1" in brief.summary
    assert "next_action=prepare_repair_execution_approval_scaffold" in brief.summary
    assert "repair_execution_enabled=0" in brief.summary
    assert "real_execution_enabled=0" in brief.summary
    assert "subprocess_enabled=0" in brief.summary


def test_global_brief_surfaces_unsupported_real_adapter_placeholder() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_real_adapter_supported": False,
            "security_real_adapter_runnable": False,
            "security_real_adapter_subprocess_supported": False,
            "security_real_adapter_requires_explicit_pr": True,
        },
    )
    text = brief.summary

    assert (
        "Real controlled retry adapter is unsupported/non-runnable: "
        "real_adapter_supported=false, real_adapter_runnable=false, "
        "subprocess_supported=false, requires_explicit_pr=true."
        in text
    )
    assert brief.key_metrics["security_real_adapter_supported"] == 0
    assert brief.key_metrics["security_real_adapter_runnable"] == 0
    assert brief.key_metrics["security_real_adapter_subprocess_supported"] == 0
    assert brief.key_metrics["security_real_adapter_requires_explicit_pr"] == 1


def test_global_brief_surfaces_rejected_real_execution_request() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_controlled_execution_real_requested": {
                "true": 1,
            },
            "security_validation_controlled_execution_real_performed": {
                "false": 1,
            },
            "security_validation_controlled_execution_real_supported": {
                "false": 1,
            },
            "security_validation_controlled_execution_subprocess_invoked": {
                "false": 1,
            },
        },
    )
    text = brief.summary

    assert (
        "Real controlled retry execution request observed and rejected: "
        "requested=1, performed=0, supported=0, subprocess_invoked=0."
        in text
    )
    assert brief.key_metrics["security_controlled_real_execution_requested"] == 1
    assert brief.key_metrics["security_controlled_real_execution_performed"] == 0
    assert brief.key_metrics["security_controlled_real_execution_supported"] == 0
    assert brief.key_metrics["security_controlled_subprocess_invoked"] == 0


def test_global_brief_surfaces_blocked_real_execution_preflight() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "security_validation_real_preflight_statuses": {
                "blocked": 1,
            },
            "security_validation_real_preflight_would_execute": {
                "false": 1,
            },
            "security_validation_real_preflight_execution_performed": {
                "false": 1,
            },
            "security_validation_real_preflight_subprocess_invoked": {
                "false": 1,
            },
            "security_validation_real_preflight_requires_explicit_pr": {
                "true": 1,
            },
        },
    )
    text = brief.summary

    assert (
        "Real execution preflight remains blocked: "
        "blocked=1, would_execute=0, execution_performed=0, "
        "subprocess_invoked=0, requires_explicit_pr=1."
        in text
    )
    assert brief.key_metrics["security_real_preflight_blocked"] == 1
    assert brief.key_metrics["security_real_preflight_would_execute"] == 0
    assert brief.key_metrics["security_real_preflight_execution_performed"] == 0
    assert brief.key_metrics["security_real_preflight_subprocess_invoked"] == 0
    assert brief.key_metrics["security_real_preflight_requires_explicit_pr"] == 1


def test_global_brief_surfaces_sandbox_adapter_scaffold_observability() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "real_execution_sandbox_adapter_scaffold_statuses": {
                "defined": 1,
            },
            "real_execution_sandbox_adapter_scaffold_fail_closed": {
                "true": 1,
            },
            "real_execution_sandbox_adapter_scaffold_deny_by_default": {
                "true": 1,
            },
            "real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_execution_performed": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_subprocess_invoked": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_real_execution_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_external_side_effects_performed": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_production_paths_mutated": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_production_secrets_accessed": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_scaffold_orphans": 0,
            "real_execution_sandbox_adapter_scaffold_linkage_complete": True,
        },
    )
    text = brief.summary

    assert "Sandbox adapter scaffold observed" in text
    assert "defined=1" in text
    assert "fail_closed=1" in text
    assert "deny_by_default=1" in text
    assert "linkage_complete=1" in text
    assert "orphans=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "execution_performed=0" in text
    assert "subprocess_invoked=0" in text
    assert "real_execution_enabled=0" in text
    assert "external_side_effects_performed=0" in text
    assert "production_paths_mutated=0" in text
    assert "production_secrets_accessed=0" in text

    assert brief.key_metrics["security_real_execution_sandbox_adapter_scaffolds"] == 1
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_scaffold_fail_closed"
        ]
        == 1
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_scaffold_deny_by_default"
        ]
        == 1
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_scaffold_execution_performed"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_scaffold_subprocess_invoked"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_scaffold_real_execution_enabled"
        ]
        == 0
    )


def test_global_brief_surfaces_sandbox_adapter_request_preflight_observability() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "real_execution_sandbox_adapter_request_preflight_statuses": {
                "blocked": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_fail_closed": {
                "true": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_deny_by_default": {
                "true": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_request_generation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_workspace_creation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_input_materialization_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_command_rendering_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_sandbox_execution_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_result_generation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_execution_performed": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_subprocess_invoked": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_real_execution_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_external_side_effects_performed": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_production_paths_mutated": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_production_secrets_accessed": {
                "false": 1,
            },
            "real_execution_sandbox_adapter_request_preflight_orphans": 0,
            "real_execution_sandbox_adapter_request_preflight_linkage_complete": True,
        },
    )
    text = brief.summary

    assert "Sandbox adapter request preflight observed" in text
    assert "blocked=1" in text
    assert "fail_closed=1" in text
    assert "deny_by_default=1" in text
    assert "linkage_complete=1" in text
    assert "orphans=0" in text
    assert "request_generation_enabled=0" in text
    assert "workspace_creation_enabled=0" in text
    assert "input_materialization_enabled=0" in text
    assert "command_rendering_enabled=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "result_generation_enabled=0" in text
    assert "execution_performed=0" in text
    assert "subprocess_invoked=0" in text
    assert "real_execution_enabled=0" in text
    assert "external_side_effects_performed=0" in text
    assert "production_paths_mutated=0" in text
    assert "production_secrets_accessed=0" in text

    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_request_preflights"
        ]
        == 1
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_request_preflight_request_generation_enabled"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_request_preflight_workspace_creation_enabled"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_request_preflight_sandbox_execution_enabled"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_adapter_request_preflight_real_execution_enabled"
        ]
        == 0
    )

def test_global_brief_surfaces_sandbox_request_envelope_scaffold_observability() -> None:
    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"overseer": 1, "security": 1}},
        security_validation={
            "security_validation_records": 1,
            "real_execution_sandbox_request_envelope_scaffold_statuses": {
                "blocked": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_fail_closed": {
                "true": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_deny_by_default": {
                "true": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_envelope_generation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_envelope_materialized": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_envelope_executable": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_request_generation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_workspace_creation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_input_materialization_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_command_rendering_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_sandbox_execution_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_result_generation_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_execution_performed": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_subprocess_invoked": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_real_execution_enabled": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_external_side_effects_performed": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_production_paths_mutated": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_production_secrets_accessed": {
                "false": 1,
            },
            "real_execution_sandbox_request_envelope_scaffold_orphans": 0,
            "real_execution_sandbox_request_envelope_scaffold_linkage_complete": True,
        },
    )
    text = brief.summary

    assert "Sandbox request envelope scaffold observed" in text
    assert "blocked=1" in text
    assert "fail_closed=1" in text
    assert "deny_by_default=1" in text
    assert "linkage_complete=1" in text
    assert "orphans=0" in text
    assert "envelope_generation_enabled=0" in text
    assert "envelope_materialized=0" in text
    assert "envelope_executable=0" in text
    assert "request_generation_enabled=0" in text
    assert "workspace_creation_enabled=0" in text
    assert "input_materialization_enabled=0" in text
    assert "command_rendering_enabled=0" in text
    assert "sandbox_execution_enabled=0" in text
    assert "result_generation_enabled=0" in text
    assert "execution_performed=0" in text
    assert "subprocess_invoked=0" in text
    assert "real_execution_enabled=0" in text
    assert "external_side_effects_performed=0" in text
    assert "production_paths_mutated=0" in text
    assert "production_secrets_accessed=0" in text

    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_request_envelope_scaffolds"
        ]
        == 1
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_request_envelope_scaffold_envelope_generation_enabled"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_request_envelope_scaffold_envelope_executable"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_request_envelope_scaffold_sandbox_execution_enabled"
        ]
        == 0
    )
    assert (
        brief.key_metrics[
            "security_real_execution_sandbox_request_envelope_scaffold_real_execution_enabled"
        ]
        == 0
    )