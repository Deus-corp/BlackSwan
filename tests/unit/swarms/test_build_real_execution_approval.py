import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_approval import (
    REAL_APPROVAL_TYPE,
    build_real_execution_approval_record,
    build_real_execution_approvals,
)


def _preflight(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_preflight",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "blocked",
        "reason": "real_execution_not_supported",
        "operator_authorized": True,
        "real_execution_requested": True,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": "python -m src.testing.run_replay_evidence_check --scenario-id s --directive-id d --timeout-profile standard",
    }
    item.update(overrides)
    return item


def test_build_real_execution_approval_record_remains_disabled() -> None:
    record = build_real_execution_approval_record(_preflight())

    assert record["type"] == REAL_APPROVAL_TYPE
    assert record["approval_status"] == "pending"
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["payload"]["real_execution_enabled"] is False
    assert record["payload"]["subprocess_enabled"] is False


def test_build_real_execution_approval_record_accepts_approved_but_disabled() -> None:
    record = build_real_execution_approval_record(
        _preflight(),
        approval_status="approved",
    )

    assert record["approval_status"] == "approved"
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False


def test_build_real_execution_approval_record_rejects_bad_status() -> None:
    with pytest.raises(ValueError, match="approval_status"):
        build_real_execution_approval_record(_preflight(), approval_status="enabled")


@pytest.mark.asyncio
async def test_build_real_execution_approvals_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_preflight())

    first = await build_real_execution_approvals(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-approval-test",
            rendered_command_id="rendered-1",
            real_execution_preflight_id="",
            approval_status="pending",
            json=False,
        )
    )
    second = await build_real_execution_approvals(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-approval-test",
            rendered_command_id="rendered-1",
            real_execution_preflight_id="",
            approval_status="pending",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["real_execution_enabled"] is False
    assert first[0]["subprocess_enabled"] is False