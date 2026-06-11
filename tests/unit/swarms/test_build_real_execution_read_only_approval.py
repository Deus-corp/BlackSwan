import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_approval import (
    REAL_READ_ONLY_APPROVAL_TYPE,
    build_real_execution_read_only_approval_record,
    build_real_execution_read_only_approvals,
)


def _final_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_final_gate",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-result-1",
        "real_execution_dry_run_envelope_id": "dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "read_only_command": "python -m src.testing.run_replay_evidence_check --scenario-id s --directive-id d --timeout-profile standard",
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
        ],
        "gate_status": "blocked",
        "reason": "read_only_execution_requires_separate_pr",
    }
    item.update(overrides)
    return item


def test_build_real_execution_read_only_approval_record_is_fail_closed_pending() -> None:
    record = build_real_execution_read_only_approval_record(_final_gate())

    assert record["type"] == REAL_READ_ONLY_APPROVAL_TYPE
    assert record["approval_status"] == "pending"
    assert record["read_only_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["rendered_command_executed"] is False
    assert record["dry_run_envelope_command_executed"] is False
    assert record["reason"] == "read_only_execution_explicit_approval_required"


def test_build_real_execution_read_only_approval_record_allows_approved_but_disabled() -> None:
    record = build_real_execution_read_only_approval_record(
        _final_gate(),
        approval_status="approved",
    )

    assert record["approval_status"] == "approved"
    assert record["read_only_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False


def test_build_real_execution_read_only_approval_record_rejects_bad_status() -> None:
    with pytest.raises(ValueError, match="unsupported approval_status"):
        build_real_execution_read_only_approval_record(
            _final_gate(),
            approval_status="enabled",
        )


@pytest.mark.asyncio
async def test_build_real_execution_read_only_approvals_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_final_gate())

    first = await build_real_execution_read_only_approvals(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-approval-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_final_gate_id="",
            approval_status="pending",
            json=False,
        )
    )
    second = await build_real_execution_read_only_approvals(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-approval-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_final_gate_id="",
            approval_status="pending",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["approval_status"] == "pending"
    assert first[0]["read_only_execution_enabled"] is False