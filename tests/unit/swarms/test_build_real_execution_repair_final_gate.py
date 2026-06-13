import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_repair_final_gate import (
    REPAIR_FINAL_GATE_TYPE,
    build_real_execution_repair_final_gate_record,
    build_real_execution_repair_final_gate_records,
)


def _transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_approval_transition",
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
        "from_status": "pending",
        "to_status": "approved",
        "source_approval_status": "pending",
        "source_review_status": "approved",
        "source_reviewed": True,
        "source_review_approved": True,
        "source_bundle_status": "assembled",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_bundle_item_count": 9,
        "source_bundle_targets": ["execution_published", "evidence_published"],
        "recommended_next_action": "prepare_repair_execution_final_gate",
        "operator_authorized": True,
        "requires_operator_review": True,
        "repair_execution_approval_required": True,
        "repair_execution_transition_approved": True,
        "repair_execution_transition_rejected": False,
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


def test_build_repair_execution_final_gate_ready_blocked_still_no_execution() -> None:
    record = build_real_execution_repair_final_gate_record(_transition())

    assert record["type"] == REPAIR_FINAL_GATE_TYPE
    assert record["gate_status"] == "ready_blocked"
    assert record["repair_preconditions_satisfied"] is True
    assert record["precondition_failures"] == []
    assert record["ready_for_repair_execution"] is False
    assert record["would_execute"] is False
    assert record["recommended_next_action"] == "prepare_repair_execution_dry_run_envelope"
    assert record["blocking_reasons"] == ["repair_execution_requires_dry_run_envelope_pr"]
    assert record["source_transition_to_status"] == "approved"
    assert record["source_transition_approved"] is True
    assert record["operator_authorized"] is True
    assert record["repair_execution_approval_required"] is True
    assert record["bundle_execution_enabled"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["bundle_execution_performed"] is False
    assert record["bundle_subprocess_invoked"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_repair_execution_final_gate_blocks_failed_preconditions() -> None:
    record = build_real_execution_repair_final_gate_record(
        _transition(source_bundle_status="unknown")
    )

    assert record["gate_status"] == "blocked"
    assert record["repair_preconditions_satisfied"] is False
    assert record["precondition_failures"] == ["source_bundle_not_assembled"]
    assert record["repair_execution_enabled"] is False
    assert record["subprocess_invoked"] is False


def test_build_repair_execution_final_gate_rejects_rejected_transition() -> None:
    with pytest.raises(
        ValueError,
        match="repair final gate requires approved repair transition",
    ):
        build_real_execution_repair_final_gate_record(
            _transition(
                to_status="rejected",
                repair_execution_transition_approved=False,
            )
        )


def test_build_repair_execution_final_gate_rejects_unauthorized_transition() -> None:
    with pytest.raises(
        ValueError,
        match="repair final gate requires operator_authorized transition",
    ):
        build_real_execution_repair_final_gate_record(
            _transition(operator_authorized=False)
        )


def test_build_repair_execution_final_gate_rejects_missing_transition_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_repair_approval_transition_id is required",
    ):
        build_real_execution_repair_final_gate_record(
            _transition(real_execution_repair_approval_transition_id="")
        )


@pytest.mark.asyncio
async def test_build_repair_execution_final_gate_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_transition())

    first = await build_real_execution_repair_final_gate_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-final-gate-test",
            rendered_command_id="rendered-1",
            real_execution_repair_approval_transition_id="",
            json=False,
        )
    )
    second = await build_real_execution_repair_final_gate_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-final-gate-test",
            rendered_command_id="rendered-1",
            real_execution_repair_approval_transition_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["gate_status"] == "ready_blocked"
    assert first[0]["repair_execution_enabled"] is False
    assert first[0]["repair_execution_performed"] is False
    assert first[0]["repair_subprocess_invoked"] is False