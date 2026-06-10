import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_final_gate import (
    REAL_FINAL_GATE_TYPE,
    build_real_execution_final_gate_record,
    build_real_execution_final_gates,
)


def _transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_approval_transition",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "from_status": "pending",
        "to_status": "approved",
        "reason": "real_execution_approval_transition_recorded",
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": "python -m src.testing.run_replay_evidence_check --scenario-id s --directive-id d --timeout-profile standard",
    }
    item.update(overrides)
    return item


def test_build_real_execution_final_gate_record_remains_blocked() -> None:
    record = build_real_execution_final_gate_record(_transition())

    assert record["type"] == REAL_FINAL_GATE_TYPE
    assert record["gate_status"] == "blocked"
    assert record["would_execute"] is False
    assert record["ready_for_real_execution"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert "explicit_execution_pr_required" in record["reasons"]


def test_build_real_execution_final_gate_requires_approved_transition() -> None:
    with pytest.raises(ValueError, match="approved transition"):
        build_real_execution_final_gate_record(_transition(to_status="rejected"))


@pytest.mark.asyncio
async def test_build_real_execution_final_gates_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_transition())

    first = await build_real_execution_final_gates(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-final-gate-test",
            rendered_command_id="rendered-1",
            real_execution_approval_transition_id="",
            json=False,
        )
    )
    second = await build_real_execution_final_gates(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-final-gate-test",
            rendered_command_id="rendered-1",
            real_execution_approval_transition_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["gate_status"] == "blocked"
    assert first[0]["ready_for_real_execution"] is False
    assert first[0]["subprocess_invoked"] is False