import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_readiness_gate import (
    REAL_READ_ONLY_READINESS_GATE_TYPE,
    build_real_execution_read_only_readiness_gate_record,
    build_real_execution_read_only_readiness_gates,
)


def _transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_approval_transition",
        "real_execution_read_only_approval_transition_id": "read-only-transition-1",
        "real_execution_read_only_approval_id": "read-only-approval-1",
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
        "from_status": "pending",
        "to_status": "approved",
        "read_only_command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id s --directive-id d --timeout-profile standard"
        ),
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
        ],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_approval_transition_recorded",
    }
    item.update(overrides)
    return item


def test_build_read_only_readiness_gate_ready_but_blocked_after_approved_transition() -> None:
    record = build_real_execution_read_only_readiness_gate_record(_transition())

    assert record["type"] == REAL_READ_ONLY_READINESS_GATE_TYPE
    assert record["read_only_approval_from_status"] == "pending"
    assert record["read_only_approval_latest_status"] == "approved"
    assert record["read_only_readiness_satisfied"] is True
    assert record["ready_for_guarded_read_only_execution"] is True
    assert record["gate_status"] == "ready_blocked"
    assert record["read_only_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["rendered_command_executed"] is False
    assert record["dry_run_envelope_command_executed"] is False
    assert record["reason"] == "guarded_read_only_execution_requires_separate_pr"


def test_build_read_only_readiness_gate_blocks_failed_preconditions() -> None:
    record = build_real_execution_read_only_readiness_gate_record(
        _transition(to_status="rejected")
    )

    assert record["read_only_readiness_satisfied"] is False
    assert record["ready_for_guarded_read_only_execution"] is False
    assert record["gate_status"] == "blocked"
    assert "read_only_transition_not_approved" in record["precondition_failures"]
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False


def test_build_read_only_readiness_gate_rejects_missing_transition_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_approval_transition_id is required",
    ):
        build_real_execution_read_only_readiness_gate_record(
            _transition(real_execution_read_only_approval_transition_id="")
        )


@pytest.mark.asyncio
async def test_build_read_only_readiness_gates_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_transition())

    first = await build_real_execution_read_only_readiness_gates(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-readiness-gate-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_approval_transition_id="",
            json=False,
        )
    )
    second = await build_real_execution_read_only_readiness_gates(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-readiness-gate-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_approval_transition_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["read_only_readiness_satisfied"] is True
    assert first[0]["gate_status"] == "ready_blocked"
    assert first[0]["read_only_execution_enabled"] is False