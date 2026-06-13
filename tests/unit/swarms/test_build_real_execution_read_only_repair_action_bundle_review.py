import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_repair_action_bundle_review import (
    READ_ONLY_REPAIR_ACTION_BUNDLE_REVIEW_TYPE,
    build_real_execution_read_only_repair_action_bundle_review_record,
    build_real_execution_read_only_repair_action_bundle_review_records,
)


def _bundle(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "real_execution_read_only_approval_transition_id": "transition-1",
        "real_execution_read_only_approval_id": "approval-1",
        "real_execution_read_only_final_gate_id": "final-gate-1",
        "real_execution_read_only_promotion_id": "promotion-1",
        "real_execution_noop_result_id": "noop-1",
        "real_execution_dry_run_envelope_id": "envelope-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "bundle_status": "assembled",
        "bundle_item_count": 2,
        "bundle_targets": ["execution_published", "evidence_published"],
        "recommended_next_action": "review_repair_action_bundle",
        "requires_operator_review": True,
        "bundle_reviewed": False,
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


def test_build_read_only_repair_action_bundle_review_pending() -> None:
    record = build_real_execution_read_only_repair_action_bundle_review_record(
        _bundle(),
        review_status="pending",
    )

    assert record["type"] == READ_ONLY_REPAIR_ACTION_BUNDLE_REVIEW_TYPE
    assert record["review_status"] == "pending"
    assert record["reviewed"] is False
    assert record["review_approved"] is False
    assert record["review_rejected"] is False
    assert record["recommended_next_action"] == "await_repair_action_bundle_review"
    assert record["operator_authorized"] is True
    assert record["requires_operator_review"] is True
    assert record["bundle_execution_enabled"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_action_bundle_review_approved_still_no_execution() -> None:
    record = build_real_execution_read_only_repair_action_bundle_review_record(
        _bundle(),
        review_status="approved",
    )

    assert record["review_status"] == "approved"
    assert record["reviewed"] is True
    assert record["review_approved"] is True
    assert record["review_rejected"] is False
    assert record["recommended_next_action"] == (
        "prepare_repair_execution_approval_scaffold"
    )
    assert record["bundle_execution_enabled"] is False
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["bundle_execution_performed"] is False
    assert record["bundle_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_action_bundle_review_rejected() -> None:
    record = build_real_execution_read_only_repair_action_bundle_review_record(
        _bundle(),
        review_status="rejected",
    )

    assert record["review_status"] == "rejected"
    assert record["reviewed"] is True
    assert record["review_approved"] is False
    assert record["review_rejected"] is True
    assert record["recommended_next_action"] == "revise_repair_action_bundle"
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_action_bundle_review_rejects_bad_status() -> None:
    with pytest.raises(
        ValueError,
        match="review_status must be one of",
    ):
        build_real_execution_read_only_repair_action_bundle_review_record(
            _bundle(),
            review_status="executed",
        )


def test_build_read_only_repair_action_bundle_review_rejects_missing_bundle_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_repair_action_bundle_id is required",
    ):
        build_real_execution_read_only_repair_action_bundle_review_record(
            _bundle(real_execution_read_only_repair_action_bundle_id="")
        )


@pytest.mark.asyncio
async def test_build_read_only_repair_action_bundle_review_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_bundle())

    first = await build_real_execution_read_only_repair_action_bundle_review_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-repair-action-bundle-review-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_repair_action_bundle_id="",
            review_status="approved",
            operator_authorized=True,
            json=False,
        )
    )
    second = await build_real_execution_read_only_repair_action_bundle_review_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-repair-action-bundle-review-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_repair_action_bundle_id="",
            review_status="approved",
            operator_authorized=True,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["review_status"] == "approved"
    assert first[0]["repair_execution_performed"] is False
    assert first[0]["repair_subprocess_invoked"] is False