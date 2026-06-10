import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_approval_transition import (
    REAL_APPROVAL_TRANSITION_TYPE,
    build_real_execution_approval_transition_record,
    build_real_execution_approval_transitions,
)


def _approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_approval",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "approval_status": "pending",
        "reason": "real_execution_explicit_approval_required",
        "operator_authorized": True,
        "real_execution_requested": True,
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


def test_build_real_execution_approval_transition_record_remains_disabled() -> None:
    record = build_real_execution_approval_transition_record(
        _approval(),
        to_status="approved",
    )

    assert record["type"] == REAL_APPROVAL_TRANSITION_TYPE
    assert record["from_status"] == "pending"
    assert record["to_status"] == "approved"
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False


def test_build_real_execution_approval_transition_record_supports_rejected() -> None:
    record = build_real_execution_approval_transition_record(
        _approval(),
        to_status="rejected",
    )

    assert record["to_status"] == "rejected"
    assert record["real_execution_enabled"] is False


def test_build_real_execution_approval_transition_rejects_non_pending_source() -> None:
    with pytest.raises(ValueError, match="only pending"):
        build_real_execution_approval_transition_record(
            _approval(approval_status="approved"),
            to_status="rejected",
        )


@pytest.mark.asyncio
async def test_build_real_execution_approval_transitions_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_approval())

    first = await build_real_execution_approval_transitions(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-approval-transition-test",
            rendered_command_id="rendered-1",
            real_execution_approval_id="",
            to_status="approved",
            json=False,
        )
    )
    second = await build_real_execution_approval_transitions(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-approval-transition-test",
            rendered_command_id="rendered-1",
            real_execution_approval_id="",
            to_status="approved",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["to_status"] == "approved"
    assert first[0]["real_execution_enabled"] is False