import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_real_execution_repair_noop_harness import (
    NOOP_MARKER,
    REPAIR_NOOP_RESULT_TYPE,
    build_real_execution_repair_noop_result_record,
    run_real_execution_repair_noop_harness_records,
)


def _envelope(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_dry_run_envelope",
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
        "repair_dry_run_status": "prepared",
        "dry_run_only": True,
        "repair_dry_run_mode": "repair_action_bundle_validation",
        "repair_dry_run_targets": ["target-a", "target-b"],
        "repair_dry_run_target_count": 2,
        "source_gate_status": "ready_blocked",
        "source_final_gate_ready_blocked": True,
        "source_final_gate_preconditions_satisfied": True,
        "source_transition_approved": True,
        "operator_authorized": True,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "recommended_next_action": "prepare_repair_execution_noop_harness",
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
    }
    item.update(overrides)
    return item


def _noop_result(**overrides):
    item = {
        "noop_argv": ["python", "-c", "print('controlled-repair-noop-ok')"],
        "exit_code": 0,
        "stdout": f"{NOOP_MARKER}\n",
        "stderr": "",
        "duration_seconds": 0.01,
    }
    item.update(overrides)
    return item


def test_build_repair_noop_result_completed_still_no_repair_execution() -> None:
    record = build_real_execution_repair_noop_result_record(
        _envelope(),
        noop_result=_noop_result(),
    )

    assert record["type"] == REPAIR_NOOP_RESULT_TYPE
    assert record["repair_noop_status"] == "completed"
    assert record["noop_only"] is True
    assert record["noop_stdout_marker_observed"] is True
    assert record["exit_code"] == 0
    assert record["source_envelope_status"] == "prepared"
    assert record["source_dry_run_only"] is True
    assert record["source_repair_dry_run_target_count"] == 2
    assert record["dry_run_envelope_executed"] is False
    assert record["repair_dry_run_envelope_executed"] is False
    assert record["repair_actions_executed"] is False
    assert record["repair_bundle_executed"] is False
    assert record["repair_command_executed"] is False
    assert record["rendered_command_executed"] is False
    assert record["dry_run_command_executed"] is False
    assert record["bundle_execution_enabled"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["bundle_execution_performed"] is False
    assert record["bundle_subprocess_invoked"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is True
    assert record["subprocess_invoked"] is True
    assert record["recommended_next_action"] == "inspect_repair_noop_result"


def test_build_repair_noop_result_failed_when_marker_missing() -> None:
    record = build_real_execution_repair_noop_result_record(
        _envelope(),
        noop_result=_noop_result(stdout="", exit_code=0),
    )

    assert record["repair_noop_status"] == "failed"
    assert record["noop_stdout_marker_observed"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert (
        record["recommended_next_action"]
        == "investigate_repair_noop_harness_failure"
    )


def test_build_repair_noop_result_rejects_repair_execution_enabled_envelope() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop harness rejects repair_execution_enabled envelope",
    ):
        build_real_execution_repair_noop_result_record(
            _envelope(repair_execution_enabled=True),
            noop_result=_noop_result(),
        )


def test_build_repair_noop_result_rejects_subprocess_invoked_envelope() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop harness rejects subprocess_invoked envelope",
    ):
        build_real_execution_repair_noop_result_record(
            _envelope(subprocess_invoked=True),
            noop_result=_noop_result(),
        )


def test_build_repair_noop_result_rejects_wrong_next_action() -> None:
    with pytest.raises(
        ValueError,
        match="repair noop harness requires noop next action",
    ):
        build_real_execution_repair_noop_result_record(
            _envelope(recommended_next_action="execute_repair"),
            noop_result=_noop_result(),
        )


@pytest.mark.asyncio
async def test_run_repair_noop_harness_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_envelope())

    first = await run_real_execution_repair_noop_harness_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-noop-harness-test",
            rendered_command_id="rendered-1",
            real_execution_repair_dry_run_envelope_id="",
            timeout_seconds=10,
            json=False,
        )
    )
    second = await run_real_execution_repair_noop_harness_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-noop-harness-test",
            rendered_command_id="rendered-1",
            real_execution_repair_dry_run_envelope_id="",
            timeout_seconds=10,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["repair_noop_status"] == "completed"
    assert first[0]["noop_only"] is True
    assert first[0]["noop_stdout_marker_observed"] is True
    assert first[0]["exit_code"] == 0
    assert first[0]["repair_actions_executed"] is False
    assert first[0]["repair_execution_performed"] is False
    assert first[0]["repair_subprocess_invoked"] is False
    assert first[0]["execution_performed"] is True
    assert first[0]["subprocess_invoked"] is True