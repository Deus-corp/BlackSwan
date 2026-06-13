import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_repair_approval import (
    REPAIR_EXECUTION_APPROVAL_TYPE,
    build_real_execution_repair_approval_record,
    build_real_execution_repair_approval_records,
)


def _review(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review",
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
        "source_bundle_status": "assembled",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_bundle_item_count": 9,
        "source_bundle_targets": ["execution_published", "evidence_published"],
        "review_status": "approved",
        "operator_authorized": True,
        "requires_operator_review": True,
        "reviewed": True,
        "review_approved": True,
        "review_rejected": False,
        "recommended_next_action": "prepare_repair_execution_approval_scaffold",
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


def test_build_repair_execution_approval_pending_scaffold() -> None:
    record = build_real_execution_repair_approval_record(
        _review(),
        approval_status="pending",
    )

    assert record["type"] == REPAIR_EXECUTION_APPROVAL_TYPE
    assert record["approval_status"] == "pending"
    assert record["source_review_status"] == "approved"
    assert record["source_reviewed"] is True
    assert record["source_review_approved"] is True
    assert record["repair_execution_approval_required"] is True
    assert record["repair_execution_approved"] is False
    assert record["repair_execution_rejected"] is False
    assert record["recommended_next_action"] == "await_repair_execution_approval"
    assert record["operator_authorized"] is True
    assert record["requires_operator_review"] is True
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


def test_build_repair_execution_approval_approved_still_no_execution() -> None:
    record = build_real_execution_repair_approval_record(
        _review(),
        approval_status="approved",
    )

    assert record["approval_status"] == "approved"
    assert record["repair_execution_approved"] is True
    assert record["recommended_next_action"] == (
        "await_repair_execution_approval_transition"
    )
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_repair_execution_approval_rejects_unapproved_review() -> None:
    with pytest.raises(ValueError, match="repair action bundle review must be approved"):
        build_real_execution_repair_approval_record(
            _review(
                review_status="pending",
                reviewed=False,
                review_approved=False,
            )
        )


def test_build_repair_execution_approval_rejects_bad_status() -> None:
    with pytest.raises(ValueError, match="approval_status must be one of"):
        build_real_execution_repair_approval_record(
            _review(),
            approval_status="executed",
        )


def test_build_repair_execution_approval_rejects_missing_review_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_repair_action_bundle_review_id is required",
    ):
        build_real_execution_repair_approval_record(
            _review(real_execution_read_only_repair_action_bundle_review_id="")
        )


@pytest.mark.asyncio
async def test_build_repair_execution_approval_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_review())

    first = await build_real_execution_repair_approval_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-approval-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_repair_action_bundle_review_id="",
            approval_status="pending",
            operator_authorized=True,
            json=False,
        )
    )
    second = await build_real_execution_repair_approval_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-approval-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_repair_action_bundle_review_id="",
            approval_status="pending",
            operator_authorized=True,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["approval_status"] == "pending"
    assert first[0]["repair_execution_enabled"] is False
    assert first[0]["repair_execution_performed"] is False
    assert first[0]["repair_subprocess_invoked"] is False