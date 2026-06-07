import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_retry_execution_eligibility import (
    build_retry_execution_eligibilities,
    build_retry_execution_eligibility,
)


def _rendered_command(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-render-test "
        "--directive-id runtime-run-replay-render-test "
        "--timeout-profile standard"
    )
    item = {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rendered",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
            "rendered_command_id": "rendered-1",
            "plan_id": "plan-1",
            "proposal_id": "proposal-1",
            "approval_id": "approval-1",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command": command,
            "execution_enabled": False,
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def _rendered_command_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_rendered_command_result",
        "rendered_command_result_id": "rendered-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "skipped",
        "reason": "execution_disabled",
        "execution_enabled": False,
        "payload": {
            "rendered_command_id": "rendered-1",
            "plan_id": "plan-1",
            "execution_enabled": False,
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def test_build_retry_execution_eligibility_blocks_disabled_command() -> None:
    eligibility = build_retry_execution_eligibility(
        _rendered_command(),
        rendered_command_result=_rendered_command_result(),
    )

    assert eligibility["type"] == "replay_lifecycle_retry_execution_eligibility"
    assert eligibility["status"] == "blocked"
    assert eligibility["reason"] == "execution_disabled"
    assert eligibility["execution_supported"] is False
    assert eligibility["execution_enabled"] is False
    assert eligibility["payload"]["executed"] is False
    assert eligibility["rendered_command_id"] == "rendered-1"


def test_build_retry_execution_eligibility_blocks_missing_result() -> None:
    eligibility = build_retry_execution_eligibility(
        _rendered_command(),
        rendered_command_result=None,
    )

    assert eligibility["status"] == "blocked"
    assert eligibility["reason"] == "missing_rendered_command_result"
    assert eligibility["execution_supported"] is False


def test_build_retry_execution_eligibility_blocks_enabled_command_as_not_supported() -> None:
    eligibility = build_retry_execution_eligibility(
        _rendered_command(execution_enabled=True),
        rendered_command_result=_rendered_command_result(
            status="rejected",
            reason="execution_not_supported",
            execution_enabled=True,
            payload={
                "rendered_command_id": "rendered-1",
                "plan_id": "plan-1",
                "execution_enabled": True,
                "executed": False,
            },
        ),
    )

    assert eligibility["status"] == "blocked"
    assert eligibility["reason"] == "execution_not_supported"
    assert eligibility["execution_supported"] is False


def test_build_retry_execution_eligibility_rejects_wrong_record_type() -> None:
    with pytest.raises(ValueError, match="rendered_command"):
        build_retry_execution_eligibility({"type": "other"})


@pytest.mark.asyncio
async def test_build_retry_execution_eligibilities_publishes_to_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())
    await crdt.add_genome(_rendered_command_result())

    eligibilities = await build_retry_execution_eligibilities(
        argparse.Namespace(
            db_path=db_path,
            source="eligibility-test",
            rendered_command_id="rendered-1",
            plan_id="",
        )
    )

    assert len(eligibilities) == 1
    assert eligibilities[0]["status"] == "blocked"
    assert eligibilities[0]["reason"] == "execution_disabled"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    stored = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_execution_eligibility"
    ]

    assert len(stored) == 1
    assert stored[0]["execution_supported"] is False


@pytest.mark.asyncio
async def test_build_retry_execution_eligibilities_skips_existing_for_rendered_command(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())
    await crdt.add_genome(_rendered_command_result())

    first = await build_retry_execution_eligibilities(
        argparse.Namespace(
            db_path=db_path,
            source="eligibility-test",
            rendered_command_id="rendered-1",
            plan_id="",
        )
    )
    second = await build_retry_execution_eligibilities(
        argparse.Namespace(
            db_path=db_path,
            source="eligibility-test",
            rendered_command_id="rendered-1",
            plan_id="",
        )
    )

    assert len(first) == 1
    assert len(second) == 0

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    stored = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_execution_eligibility"
        and item.get("rendered_command_id") == "rendered-1"
    ]

    assert len(stored) == 1
    assert stored[0]["status"] == "blocked"
    assert stored[0]["reason"] == "execution_disabled"