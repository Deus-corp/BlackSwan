import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_repair_readiness_gate import (
    REPAIR_READINESS_GATE_TYPE,
    build_real_execution_repair_readiness_gate_record,
    build_real_execution_repair_readiness_gate_records,
)


def _feedback(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_noop_feedback",
        "real_execution_repair_noop_feedback_id": "repair-feedback-1",
        "real_execution_repair_noop_result_id": "repair-noop-1",
        "real_execution_repair_dry_run_envelope_id": "repair-envelope-1",
        "real_execution_repair_final_gate_id": "repair-final-gate-1",
        "real_execution_repair_approval_transition_id": "repair-transition-1",
        "real_execution_repair_approval_id": "repair-approval-1",
        "real_execution_read_only_repair_action_bundle_review_id": "bundle-review-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "real_execution_read_only_approval_transition_id": "read-only-transition-1",
        "real_execution_read_only_approval_id": "read-only-approval-1",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-1",
        "real_execution_dry_run_envelope_id": "envelope-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "feedback_status": "actionable",
        "repair_noop_verified": True,
        "repair_path_can_proceed": True,
        "repair_path_next_gate_allowed": True,
        "recommended_next_action": "prepare_repair_execution_readiness_gate",
        "source_noop_status": "completed",
        "source_noop_exit_code": 0,
        "source_noop_only": True,
        "source_noop_stdout_marker_observed": True,
        "source_execution_performed": True,
        "source_subprocess_invoked": True,
        "source_envelope_status": "prepared",
        "source_dry_run_only": True,
        "source_repair_dry_run_mode": "repair_action_bundle_validation",
        "source_repair_dry_run_target_count": 3,
        "source_repair_dry_run_targets": [
            "directive_seeded",
            "evidence_published",
            "execution_completed",
        ],
        "source_final_gate_ready_blocked": True,
        "source_transition_approved": True,
        "operator_authorized": True,
        "source_repair_actions_executed": False,
        "source_repair_bundle_executed": False,
        "source_repair_command_executed": False,
        "source_repair_execution_enabled": False,
        "source_repair_execution_performed": False,
        "source_repair_subprocess_invoked": False,
        "feedback_execution_performed": False,
        "feedback_subprocess_invoked": False,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_noop_feedback_recorded",
    }
    item.update(overrides)
    return item


def test_build_repair_readiness_gate_ready_blocked_still_no_repair_execution() -> None:
    record = build_real_execution_repair_readiness_gate_record(_feedback())

    assert record["type"] == REPAIR_READINESS_GATE_TYPE
    assert record["gate_status"] == "ready_blocked"
    assert record["repair_readiness_satisfied"] is True
    assert record["ready_for_guarded_repair_execution"] is True
    assert record["ready_for_repair_execution"] is False
    assert record["would_execute"] is False
    assert record["blocking_reasons"] == [
        "guarded_repair_execution_requires_separate_pr"
    ]
    assert record["recommended_next_action"] == "prepare_guarded_repair_execution_harness"
    assert record["source_feedback_status"] == "actionable"
    assert record["source_repair_noop_verified"] is True
    assert record["source_repair_path_can_proceed"] is True
    assert record["source_repair_path_next_gate_allowed"] is True
    assert record["source_noop_status"] == "completed"
    assert record["source_noop_exit_code"] == 0
    assert record["source_execution_performed"] is True
    assert record["source_subprocess_invoked"] is True
    assert record["source_repair_dry_run_target_count"] == 3
    assert record["source_repair_actions_executed"] is False
    assert record["source_repair_execution_enabled"] is False
    assert record["source_repair_execution_performed"] is False
    assert record["source_repair_subprocess_invoked"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_repair_readiness_gate_rejects_non_actionable_feedback() -> None:
    with pytest.raises(
        ValueError,
        match="repair readiness gate requires actionable feedback",
    ):
        build_real_execution_repair_readiness_gate_record(
            _feedback(feedback_status="blocked")
        )


def test_build_repair_readiness_gate_rejects_path_not_allowed() -> None:
    with pytest.raises(
        ValueError,
        match="repair readiness gate requires next gate allowed",
    ):
        build_real_execution_repair_readiness_gate_record(
            _feedback(repair_path_next_gate_allowed=False)
        )


def test_build_repair_readiness_gate_rejects_source_repair_actions_executed() -> None:
    with pytest.raises(
        ValueError,
        match="repair readiness gate rejects source repair actions executed",
    ):
        build_real_execution_repair_readiness_gate_record(
            _feedback(source_repair_actions_executed=True)
        )


def test_build_repair_readiness_gate_rejects_feedback_subprocess_invoked() -> None:
    with pytest.raises(
        ValueError,
        match="repair readiness gate rejects feedback subprocess invoked",
    ):
        build_real_execution_repair_readiness_gate_record(
            _feedback(feedback_subprocess_invoked=True)
        )


def test_build_repair_readiness_gate_rejects_repair_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="repair readiness gate rejects repair execution enabled",
    ):
        build_real_execution_repair_readiness_gate_record(
            _feedback(repair_execution_enabled=True)
        )


@pytest.mark.asyncio
async def test_build_repair_readiness_gate_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_feedback())

    first = await build_real_execution_repair_readiness_gate_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-readiness-gate-test",
            rendered_command_id="rendered-1",
            real_execution_repair_noop_feedback_id="",
            json=False,
        )
    )
    second = await build_real_execution_repair_readiness_gate_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-readiness-gate-test",
            rendered_command_id="rendered-1",
            real_execution_repair_noop_feedback_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["gate_status"] == "ready_blocked"
    assert first[0]["repair_readiness_satisfied"] is True
    assert first[0]["ready_for_guarded_repair_execution"] is True
    assert first[0]["repair_execution_enabled"] is False
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False