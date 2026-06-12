import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_feedback import (
    READ_ONLY_FEEDBACK_TYPE,
    build_real_execution_read_only_feedback_record,
    build_real_execution_read_only_feedback_records,
)


def _execution_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_execution_result",
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
        "status": "failed",
        "reason": "guarded_read_only_execution_failed",
        "operator_authorized": True,
        "allow_guarded_read_only_execution": True,
        "read_only_execution_enabled": True,
        "real_execution_enabled": False,
        "subprocess_invoked": True,
        "execution_performed": True,
        "read_only_command_executed": True,
        "rendered_command_executed": True,
        "dry_run_envelope_command_executed": True,
        "exit_code": 1,
        "stdout": "execution_published failed\n",
        "stderr": "visibility_crdt_trail_complete failed\n",
        "validation_reasons": [],
    }
    item.update(overrides)
    return item


def test_build_read_only_feedback_records_failed_execution_as_actionable() -> None:
    record = build_real_execution_read_only_feedback_record(_execution_result())

    assert record["type"] == READ_ONLY_FEEDBACK_TYPE
    assert record["source_status"] == "failed"
    assert record["source_exit_code"] == 1
    assert record["feedback_status"] == "actionable"
    assert (
        record["recommended_next_action"]
        == "investigate_failed_read_only_evidence_check"
    )
    assert record["read_only_execution_was_observed"] is True
    assert record["read_only_execution_failed"] is True
    assert record["read_only_execution_succeeded"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert "observed_marker:execution_published" in record["failure_hints"]
    assert "observed_marker:visibility_crdt_trail_complete" in record["failure_hints"]


def test_build_read_only_feedback_records_successful_execution() -> None:
    record = build_real_execution_read_only_feedback_record(
        _execution_result(
            status="executed",
            reason="guarded_read_only_execution_completed",
            exit_code=0,
            stdout="ok\n",
            stderr="",
        )
    )

    assert record["feedback_status"] == "successful"
    assert (
        record["recommended_next_action"]
        == "promote_successful_read_only_execution_evidence"
    )
    assert record["read_only_execution_succeeded"] is True
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_feedback_records_rejected_execution_as_blocked() -> None:
    record = build_real_execution_read_only_feedback_record(
        _execution_result(
            status="rejected",
            reason="guarded_read_only_execution_rejected",
            exit_code=None,
            read_only_execution_enabled=False,
            subprocess_invoked=False,
            execution_performed=False,
            read_only_command_executed=False,
            rendered_command_executed=False,
            dry_run_envelope_command_executed=False,
            validation_reasons=["guarded_read_only_execution_flag_required"],
        )
    )

    assert record["feedback_status"] == "blocked"
    assert (
        record["recommended_next_action"]
        == "resolve_guarded_read_only_execution_rejection"
    )
    assert record["read_only_execution_rejected"] is True
    assert "validation_reasons_present" in record["failure_hints"]
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_read_only_feedback_rejects_missing_execution_result_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_execution_result_id is required",
    ):
        build_real_execution_read_only_feedback_record(
            _execution_result(real_execution_read_only_execution_result_id="")
        )


@pytest.mark.asyncio
async def test_build_read_only_feedback_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_execution_result())

    first = await build_real_execution_read_only_feedback_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-feedback-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_execution_result_id="",
            json=False,
        )
    )
    second = await build_real_execution_read_only_feedback_records(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-feedback-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_execution_result_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["feedback_status"] == "actionable"
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False