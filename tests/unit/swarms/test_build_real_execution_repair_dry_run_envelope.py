import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_repair_dry_run_envelope import (
    REPAIR_DRY_RUN_ENVELOPE_TYPE,
    build_real_execution_repair_dry_run_envelope_record,
    build_real_execution_repair_dry_run_envelope_records,
)


def _final_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_final_gate",
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
        "repair_preconditions_satisfied": True,
        "precondition_failures": [],
        "ready_for_repair_execution": False,
        "would_execute": False,
        "recommended_next_action": "prepare_repair_execution_dry_run_envelope",
        "source_transition_to_status": "approved",
        "source_transition_approved": True,
        "source_review_status": "approved",
        "source_bundle_status": "assembled",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_bundle_item_count": 9,
        "source_bundle_targets": [
            "directive_seeded",
            "evidence_published",
            "execution_completed",
        ],
        "operator_authorized": True,
        "requires_operator_review": True,
        "repair_execution_approval_required": True,
        "repair_execution_transition_approved": True,
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


def test_build_repair_execution_dry_run_envelope_prepared_still_no_execution() -> None:
    record = build_real_execution_repair_dry_run_envelope_record(_final_gate())

    assert record["type"] == REPAIR_DRY_RUN_ENVELOPE_TYPE
    assert record["repair_dry_run_status"] == "prepared"
    assert record["dry_run_only"] is True
    assert record["repair_dry_run_mode"] == "repair_action_bundle_validation"
    assert record["repair_dry_run_target_count"] == 3
    assert record["repair_dry_run_report"]["applies_changes"] is False
    assert record["repair_dry_run_report"]["invokes_subprocess"] is False
    assert record["repair_dry_run_report"]["executes_bundle"] is False
    assert record["source_gate_status"] == "ready_blocked"
    assert record["source_final_gate_preconditions_satisfied"] is True
    assert record["source_transition_approved"] is True
    assert record["ready_for_repair_execution"] is False
    assert record["would_execute"] is False
    assert record["recommended_next_action"] == "prepare_repair_execution_noop_harness"
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


def test_build_repair_execution_dry_run_envelope_rejects_non_ready_gate() -> None:
    with pytest.raises(
        ValueError,
        match="repair dry-run envelope requires ready_blocked final gate",
    ):
        build_real_execution_repair_dry_run_envelope_record(
            _final_gate(gate_status="blocked")
        )


def test_build_repair_execution_dry_run_envelope_rejects_unsatisfied_preconditions() -> None:
    with pytest.raises(
        ValueError,
        match="repair dry-run envelope requires satisfied preconditions",
    ):
        build_real_execution_repair_dry_run_envelope_record(
            _final_gate(repair_preconditions_satisfied=False)
        )


def test_build_repair_execution_dry_run_envelope_rejects_wrong_next_action() -> None:
    with pytest.raises(
        ValueError,
        match="repair dry-run envelope requires final gate dry-run action",
    ):
        build_real_execution_repair_dry_run_envelope_record(
            _final_gate(recommended_next_action="execute_repair")
        )


def test_build_repair_execution_dry_run_envelope_rejects_missing_final_gate_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_repair_final_gate_id is required",
    ):
        build_real_execution_repair_dry_run_envelope_record(
            _final_gate(real_execution_repair_final_gate_id="")
        )


@pytest.mark.asyncio
async def test_build_repair_execution_dry_run_envelope_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_final_gate())

    first = await build_real_execution_repair_dry_run_envelope_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-dry-run-envelope-test",
            rendered_command_id="rendered-1",
            real_execution_repair_final_gate_id="",
            json=False,
        )
    )
    second = await build_real_execution_repair_dry_run_envelope_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-repair-dry-run-envelope-test",
            rendered_command_id="rendered-1",
            real_execution_repair_final_gate_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["repair_dry_run_status"] == "prepared"
    assert first[0]["dry_run_only"] is True
    assert first[0]["repair_execution_enabled"] is False
    assert first[0]["repair_execution_performed"] is False
    assert first[0]["repair_subprocess_invoked"] is False