import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_repair_plan import (
    READ_ONLY_REPAIR_PLAN_TYPE,
    build_real_execution_read_only_repair_plan_record,
    build_real_execution_read_only_repair_plan_records,
)


def _feedback(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_feedback",
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
        "source_status": "failed",
        "source_reason": "guarded_read_only_execution_failed",
        "source_exit_code": 1,
        "feedback_status": "actionable",
        "recommended_next_action": "investigate_failed_read_only_evidence_check",
        "failure_hints": [
            "observed_marker:execution_published",
            "observed_marker:execution_completed",
            "observed_marker:evidence_published",
            "observed_marker:memory_record_published",
            "observed_marker:visibility_crdt_trail_complete",
            "source_status:failed",
            "source_exit_code:1",
        ],
        "read_only_execution_was_observed": True,
        "read_only_execution_failed": True,
        "read_only_execution_succeeded": False,
        "read_only_execution_rejected": False,
        "real_execution_enabled": False,
        "feedback_execution_performed": False,
        "feedback_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
    }
    item.update(overrides)
    return item


def test_build_read_only_repair_plan_from_actionable_feedback() -> None:
    record = build_real_execution_read_only_repair_plan_record(_feedback())

    assert record["type"] == READ_ONLY_REPAIR_PLAN_TYPE
    assert record["repair_plan_status"] == "planned"
    assert record["source_feedback_status"] == "actionable"
    assert record["source_status"] == "failed"
    assert record["source_exit_code"] == 1
    assert record["repair_item_count"] >= 4
    assert "execution_published" in record["repair_targets"]
    assert "evidence_published" in record["repair_targets"]
    assert record["recommended_next_action"] == "review_replay_evidence_repair_plan"
    assert record["requires_operator_review"] is True
    assert record["repair_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["repair_execution_performed"] is False
    assert record["repair_subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_plan_for_successful_feedback() -> None:
    record = build_real_execution_read_only_repair_plan_record(
        _feedback(
            source_status="executed",
            source_exit_code=0,
            feedback_status="successful",
            recommended_next_action="promote_successful_read_only_execution_evidence",
            read_only_execution_failed=False,
            read_only_execution_succeeded=True,
            failure_hints=[],
        )
    )

    assert record["repair_plan_status"] == "no_repair_needed"
    assert record["repair_item_count"] == 1
    assert record["repair_targets"] == ["successful_read_only_execution"]
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_plan_for_rejected_feedback() -> None:
    record = build_real_execution_read_only_repair_plan_record(
        _feedback(
            source_status="rejected",
            source_exit_code=None,
            feedback_status="blocked",
            recommended_next_action="resolve_guarded_read_only_execution_rejection",
            read_only_execution_failed=False,
            read_only_execution_rejected=True,
            failure_hints=["validation_reasons_present"],
        )
    )

    assert record["repair_plan_status"] == "blocked"
    assert record["repair_targets"] == ["guarded_read_only_execution_rejection"]
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_repair_plan_rejects_missing_feedback_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_feedback_id is required",
    ):
        build_real_execution_read_only_repair_plan_record(
            _feedback(real_execution_read_only_feedback_id="")
        )


@pytest.mark.asyncio
async def test_build_read_only_repair_plan_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_feedback())

    first = await build_real_execution_read_only_repair_plan_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-repair-plan-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_feedback_id="",
            json=False,
        )
    )
    second = await build_real_execution_read_only_repair_plan_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-repair-plan-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_feedback_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["repair_plan_status"] == "planned"
    assert first[0]["repair_execution_performed"] is False
    assert first[0]["repair_subprocess_invoked"] is False