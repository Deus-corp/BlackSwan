import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_post_repair_evidence_check import (
    POST_REPAIR_EVIDENCE_CHECK_TYPE,
    POST_REPAIR_EVIDENCE_MARKER,
    build_post_repair_evidence_check_record,
    run_post_repair_evidence_check_records,
)


def _guarded_result(**overrides):
    targets = [
        "directive_seeded",
        "evidence_published",
        "execution_completed",
    ]
    item = {
        "type": "replay_lifecycle_retry_guarded_repair_execution_result",
        "guarded_repair_execution_result_id": "guarded-repair-result-1",
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
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "repair_execution_status": "succeeded",
        "repair_execution_allowed": True,
        "guarded_repair_execution": True,
        "guarded_repair_marker_observed": True,
        "exit_code": 0,
        "recommended_next_action": "run_post_repair_evidence_check",
        "source_gate_status": "ready_blocked",
        "source_repair_readiness_satisfied": True,
        "source_ready_for_guarded_repair_execution": True,
        "source_ready_for_repair_execution": False,
        "source_would_execute": False,
        "source_feedback_status": "actionable",
        "source_repair_noop_verified": True,
        "source_repair_path_can_proceed": True,
        "source_repair_path_next_gate_allowed": True,
        "source_noop_status": "completed",
        "source_noop_exit_code": 0,
        "source_execution_performed": True,
        "source_subprocess_invoked": True,
        "source_repair_dry_run_target_count": 3,
        "source_repair_dry_run_targets": targets,
        "operator_authorized": True,
        "repair_action_results": [
            {"target": target, "status": "completed"} for target in targets
        ],
        "repair_action_target_count": 3,
        "repair_actions_executed": True,
        "repair_bundle_executed": True,
        "repair_command_executed": True,
        "rendered_command_executed": False,
        "dry_run_command_executed": False,
        "bundle_execution_enabled": True,
        "repair_execution_enabled": True,
        "real_execution_enabled": False,
        "subprocess_enabled": True,
        "bundle_execution_performed": True,
        "bundle_subprocess_invoked": True,
        "repair_execution_performed": True,
        "repair_subprocess_invoked": True,
        "execution_performed": True,
        "subprocess_invoked": True,
        "reason": "guarded_repair_execution_succeeded",
    }
    item.update(overrides)
    return item


def _subprocess_result(**overrides):
    item = {
        "evidence_argv": ["python", "-c", "print('post-repair-evidence-ok')"],
        "exit_code": 0,
        "stdout": f"{POST_REPAIR_EVIDENCE_MARKER}\n",
        "stderr": "",
        "duration_seconds": 0.01,
    }
    item.update(overrides)
    return item


def test_build_post_repair_evidence_check_rejects_without_allow_flag() -> None:
    record = build_post_repair_evidence_check_record(
        _guarded_result(),
        allow_post_repair_evidence_check=False,
    )

    assert record["type"] == POST_REPAIR_EVIDENCE_CHECK_TYPE
    assert record["post_repair_status"] == "rejected"
    assert record["post_repair_evidence_check_allowed"] is False
    assert record["post_repair_evidence_check_enabled"] is False
    assert record["repair_outcome_verified"] is False
    assert record["evidence_check_execution_performed"] is False
    assert record["evidence_check_subprocess_invoked"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["recommended_next_action"] == "authorize_post_repair_evidence_check"


def test_build_post_repair_evidence_check_passes_with_allow_flag() -> None:
    record = build_post_repair_evidence_check_record(
        _guarded_result(),
        allow_post_repair_evidence_check=True,
        subprocess_result=_subprocess_result(),
    )

    assert record["type"] == POST_REPAIR_EVIDENCE_CHECK_TYPE
    assert record["post_repair_status"] == "passed"
    assert record["post_repair_evidence_check_allowed"] is True
    assert record["post_repair_evidence_check_enabled"] is True
    assert record["post_repair_evidence_marker_observed"] is True
    assert record["post_repair_evidence_exit_code"] == 0
    assert record["repair_outcome_verified"] is True
    assert record["repair_targets_expected_count"] == 3
    assert record["repair_targets_verified_count"] == 3
    assert record["repair_targets_missing"] == []
    assert record["repair_targets_unexpected"] == []
    assert record["source_guarded_repair_execution_status"] == "succeeded"
    assert record["source_repair_actions_executed"] is True
    assert record["source_repair_execution_enabled"] is True
    assert record["source_real_execution_enabled"] is False
    assert record["evidence_check_execution_performed"] is True
    assert record["evidence_check_subprocess_invoked"] is True
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is True
    assert record["subprocess_invoked"] is True
    assert record["recommended_next_action"] == "close_repair_loop"


def test_build_post_repair_evidence_check_fails_when_marker_missing() -> None:
    record = build_post_repair_evidence_check_record(
        _guarded_result(),
        allow_post_repair_evidence_check=True,
        subprocess_result=_subprocess_result(stdout="", exit_code=0),
    )

    assert record["post_repair_status"] == "failed"
    assert record["post_repair_evidence_marker_observed"] is False
    assert record["repair_outcome_verified"] is False
    assert record["recommended_next_action"] == "investigate_post_repair_failure"


def test_build_post_repair_evidence_check_rejects_non_succeeded_guarded_result() -> None:
    with pytest.raises(
        ValueError,
        match="post-repair evidence check requires succeeded repair result",
    ):
        build_post_repair_evidence_check_record(
            _guarded_result(repair_execution_status="failed"),
            allow_post_repair_evidence_check=True,
            subprocess_result=_subprocess_result(),
        )


def test_build_post_repair_evidence_check_rejects_missing_completed_target() -> None:
    targets = [
        "directive_seeded",
        "evidence_published",
        "execution_completed",
    ]
    with pytest.raises(
        ValueError,
        match="post-repair evidence check requires completed repair targets",
    ):
        build_post_repair_evidence_check_record(
            _guarded_result(
                repair_action_results=[
                    {"target": targets[0], "status": "completed"},
                    {"target": targets[1], "status": "completed"},
                    {"target": targets[2], "status": "not_executed"},
                ]
            ),
            allow_post_repair_evidence_check=True,
            subprocess_result=_subprocess_result(),
        )


def test_build_post_repair_evidence_check_rejects_real_execution_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="post-repair evidence check rejects real execution enabled",
    ):
        build_post_repair_evidence_check_record(
            _guarded_result(real_execution_enabled=True),
            allow_post_repair_evidence_check=True,
            subprocess_result=_subprocess_result(),
        )


@pytest.mark.asyncio
async def test_run_post_repair_evidence_check_publishes_allowed_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_guarded_result())

    first = await run_post_repair_evidence_check_records(
        argparse.Namespace(
            db_path=db_path,
            source="post-repair-evidence-check-test",
            rendered_command_id="rendered-1",
            guarded_repair_execution_result_id="",
            allow_post_repair_evidence_check=True,
            timeout_seconds=10,
            json=False,
        )
    )
    second = await run_post_repair_evidence_check_records(
        argparse.Namespace(
            db_path=db_path,
            source="post-repair-evidence-check-test",
            rendered_command_id="rendered-1",
            guarded_repair_execution_result_id="",
            allow_post_repair_evidence_check=True,
            timeout_seconds=10,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["post_repair_status"] == "passed"
    assert first[0]["repair_outcome_verified"] is True
    assert first[0]["post_repair_evidence_marker_observed"] is True
    assert first[0]["repair_targets_verified_count"] == 3
    assert first[0]["repair_execution_enabled"] is False
    assert first[0]["real_execution_enabled"] is False
    assert first[0]["repair_execution_performed"] is False