import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_repair_noop_feedback import (
    REPAIR_NOOP_FEEDBACK_TYPE,
    build_real_execution_repair_noop_feedback_record,
    build_real_execution_repair_noop_feedback_records,
)


def _noop_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_noop_result",
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
        "repair_noop_status": "completed",
        "noop_only": True,
        "noop_stdout_marker_observed": True,
        "exit_code": 0,
        "stdout": "controlled-repair-noop-ok\n",
        "stderr": "",
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
        "dry_run_envelope_executed": False,
        "repair_dry_run_envelope_executed": False,
        "repair_actions_executed": False,
        "repair_bundle_executed": False,
        "repair_command_executed": False,
        "rendered_command_executed": False,
        "dry_run_command_executed": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": True,
        "subprocess_invoked": True,
        "recommended_next_action": "inspect_repair_noop_result",
        "reason": "repair_execution_noop_harness_completed",
    }
    item.update(overrides)
    return item


def test_build_repair_noop_feedback_actionable_still_no_repair_execution() -> None:
    record = build_real_execution_repair_noop_feedback_record(_noop_result())

    assert record["type"] == REPAIR_NOOP_FEEDBACK_TYPE
    assert record["feedback_status"] == "actionable"
    assert record["repair_noop_verified"] is True
    assert record["repair_path_can_proceed"] is True
    assert record["repair_path_next_gate_allowed"] is True
    assert record["recommended_next_action"] == "prepare_repair_execution_readiness_gate"
    assert record["source_noop_status"] == "completed"
    assert record["source_noop_exit_code"] == 0
    assert record["source_noop_only"] is True
    assert record["source_noop_stdout_marker_observed"] is True
    assert record["source_execution_performed"] is True
    assert record["source_subprocess_invoked"] is True
    assert record["source_repair_dry_run_target_count"] == 3
    assert record["source_repair_actions_executed"] is False
    assert record["source_repair_execution_enabled"] is False
    assert record["source_repair_execution_performed"] is False
    assert record["source_repair_subprocess_invoked"] is False
    assert record["feedback_execution_performed"] is False
    assert record["feedback_subprocess_invoked"] is False
    assert record["ready_for_repair_execution"] is False
    assert record["would_execute"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_repair_noop_feedback_rejects_failed_noop_result() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop feedback requires completed noop result",
    ):
        build_real_execution_repair_noop_feedback_record(
            _noop_result(repair_noop_status="failed")
        )


def test_build_repair_noop_feedback_rejects_repair_actions_executed() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop feedback rejects repair_actions_executed result",
    ):
        build_real_execution_repair_noop_feedback_record(
            _noop_result(repair_actions_executed=True)
        )


def test_build_repair_noop_feedback_rejects_repair_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop feedback rejects repair_execution_enabled result",
    ):
        build_real_execution_repair_noop_feedback_record(
            _noop_result(repair_execution_enabled=True)
        )


def test_build_repair_noop_feedback_rejects_missing_stdout_marker() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop feedback requires stdout marker",
    ):
        build_real_execution_repair_noop_feedback_record(
            _noop_result(noop_stdout_marker_observed=False)
        )


def test_build_repair_noop_feedback_rejects_missing_source_targets() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop feedback requires source repair targets",
    ):
        build_real_execution_repair_noop_feedback_record(
            _noop_result(source_repair_dry_run_target_count=0)
        )


@pytest.mark.asyncio
async def test_build_repair_noop_feedback_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_noop_result())

    first = await build_real_execution_repair_noop_feedback_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-noop-feedback-test",
            rendered_command_id="rendered-1",
            real_execution_repair_noop_result_id="",
            json=False,
        )
    )
    second = await build_real_execution_repair_noop_feedback_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-noop-feedback-test",
            rendered_command_id="rendered-1",
            real_execution_repair_noop_result_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["feedback_status"] == "actionable"
    assert first[0]["repair_path_can_proceed"] is True
    assert first[0]["repair_execution_enabled"] is False
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False