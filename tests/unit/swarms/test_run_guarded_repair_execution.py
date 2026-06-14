import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_guarded_repair_execution import (
    GUARDED_REPAIR_MARKER,
    REPAIR_EXECUTION_RESULT_TYPE,
    build_guarded_repair_execution_result_record,
    run_guarded_repair_execution_records,
)


def _gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_readiness_gate",
        "real_execution_repair_readiness_gate_id": "repair-readiness-gate-1",
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
        "gate_status": "ready_blocked",
        "repair_readiness_satisfied": True,
        "ready_for_guarded_repair_execution": True,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "blocking_reasons": ["guarded_repair_execution_requires_separate_pr"],
        "recommended_next_action": "prepare_guarded_repair_execution_harness",
        "source_feedback_status": "actionable",
        "source_repair_noop_verified": True,
        "source_repair_path_can_proceed": True,
        "source_repair_path_next_gate_allowed": True,
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
        "reason": "repair_execution_readiness_gate_recorded",
    }
    item.update(overrides)
    return item


def _subprocess_result(**overrides):
    item = {
        "repair_argv": ["python", "-c", "print('guarded-repair-execution-ok')"],
        "exit_code": 0,
        "stdout": f"{GUARDED_REPAIR_MARKER}\n",
        "stderr": "",
        "duration_seconds": 0.01,
    }
    item.update(overrides)
    return item


def test_build_guarded_repair_execution_rejects_without_allow_flag() -> None:
    record = build_guarded_repair_execution_result_record(
        _gate(),
        allow_guarded_repair_execution=False,
    )

    assert record["type"] == REPAIR_EXECUTION_RESULT_TYPE
    assert record["repair_execution_status"] == "rejected"
    assert record["repair_execution_allowed"] is False
    assert record["repair_actions_executed"] is False
    assert record["repair_bundle_executed"] is False
    assert record["repair_command_executed"] is False
    assert record["rendered_command_executed"] is False
    assert record["dry_run_command_executed"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["recommended_next_action"] == "authorize_guarded_repair_execution"


def test_build_guarded_repair_execution_succeeds_with_allow_flag() -> None:
    record = build_guarded_repair_execution_result_record(
        _gate(),
        allow_guarded_repair_execution=True,
        subprocess_result=_subprocess_result(),
    )

    assert record["type"] == REPAIR_EXECUTION_RESULT_TYPE
    assert record["repair_execution_status"] == "succeeded"
    assert record["repair_execution_allowed"] is True
    assert record["guarded_repair_marker_observed"] is True
    assert record["exit_code"] == 0
    assert record["repair_action_target_count"] == 3
    assert record["repair_actions_executed"] is True
    assert record["repair_bundle_executed"] is True
    assert record["repair_command_executed"] is True
    assert record["rendered_command_executed"] is False
    assert record["dry_run_command_executed"] is False
    assert record["bundle_execution_enabled"] is True
    assert record["repair_execution_enabled"] is True
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is True
    assert record["bundle_execution_performed"] is True
    assert record["bundle_subprocess_invoked"] is True
    assert record["repair_execution_performed"] is True
    assert record["repair_subprocess_invoked"] is True
    assert record["execution_performed"] is True
    assert record["subprocess_invoked"] is True
    assert record["recommended_next_action"] == "run_post_repair_evidence_check"


def test_build_guarded_repair_execution_failed_when_marker_missing() -> None:
    record = build_guarded_repair_execution_result_record(
        _gate(),
        allow_guarded_repair_execution=True,
        subprocess_result=_subprocess_result(stdout="", exit_code=0),
    )

    assert record["repair_execution_status"] == "failed"
    assert record["guarded_repair_marker_observed"] is False
    assert record["repair_actions_executed"] is False
    assert record["repair_execution_performed"] is False
    assert record["recommended_next_action"] == "investigate_guarded_repair_execution_failure"


def test_build_guarded_repair_execution_rejects_gate_without_guarded_ready() -> None:
    with pytest.raises(
        ValueError,
        match="guarded repair execution requires guarded readiness",
    ):
        build_guarded_repair_execution_result_record(
            _gate(ready_for_guarded_repair_execution=False),
            allow_guarded_repair_execution=True,
            subprocess_result=_subprocess_result(),
        )


def test_build_guarded_repair_execution_rejects_gate_with_repair_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="guarded repair execution rejects repair_execution_enabled gate",
    ):
        build_guarded_repair_execution_result_record(
            _gate(repair_execution_enabled=True),
            allow_guarded_repair_execution=True,
            subprocess_result=_subprocess_result(),
        )


def test_build_guarded_repair_execution_rejects_source_repair_actions_executed() -> None:
    with pytest.raises(
        ValueError,
        match="guarded repair execution rejects source repair actions executed",
    ):
        build_guarded_repair_execution_result_record(
            _gate(source_repair_actions_executed=True),
            allow_guarded_repair_execution=True,
            subprocess_result=_subprocess_result(),
        )


@pytest.mark.asyncio
async def test_run_guarded_repair_execution_publishes_allowed_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_gate())

    first = await run_guarded_repair_execution_records(
        argparse.Namespace(
            db_path=db_path,
            source="guarded-repair-execution-test",
            rendered_command_id="rendered-1",
            real_execution_repair_readiness_gate_id="",
            allow_guarded_repair_execution=True,
            timeout_seconds=10,
            json=False,
        )
    )
    second = await run_guarded_repair_execution_records(
        argparse.Namespace(
            db_path=db_path,
            source="guarded-repair-execution-test",
            rendered_command_id="rendered-1",
            real_execution_repair_readiness_gate_id="",
            allow_guarded_repair_execution=True,
            timeout_seconds=10,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["repair_execution_status"] == "succeeded"
    assert first[0]["repair_execution_allowed"] is True
    assert first[0]["guarded_repair_marker_observed"] is True
    assert first[0]["repair_actions_executed"] is True
    assert first[0]["rendered_command_executed"] is False
    assert first[0]["real_execution_enabled"] is False