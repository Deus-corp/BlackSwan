import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_rendered_retry_commands import (
    build_rendered_retry_command_result,
    run_rendered_retry_commands,
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
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rendered",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
            "rendered_command_id": "rendered-command-1",
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


def test_build_rendered_retry_command_result_skips_disabled_command() -> None:
    result = build_rendered_retry_command_result(_rendered_command())

    assert result["type"] == "replay_lifecycle_retry_rendered_command_result"
    assert result["status"] == "skipped"
    assert result["reason"] == "execution_disabled"
    assert result["execution_enabled"] is False
    assert result["payload"]["executed"] is False
    assert result["rendered_command_id"] == "rendered-command-1"
    assert result["plan_id"] == "plan-1"


def test_build_rendered_retry_command_result_rejects_enabled_command() -> None:
    result = build_rendered_retry_command_result(
        _rendered_command(execution_enabled=True)
    )

    assert result["status"] == "rejected"
    assert result["reason"] == "execution_not_supported"
    assert result["execution_enabled"] is True
    assert result["payload"]["executed"] is False


def test_build_rendered_retry_command_result_rejects_missing_rendered_command_id() -> None:
    with pytest.raises(ValueError, match="rendered_command_id"):
        build_rendered_retry_command_result(
            _rendered_command(rendered_command_id="")
        )


@pytest.mark.asyncio
async def test_run_rendered_retry_commands_publishes_result(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    results = await run_rendered_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="rendered-retry-command-runner-test",
            rendered_command_id="",
            plan_id="",
        )
    )

    assert len(results) == 1
    assert results[0]["status"] == "skipped"
    assert results[0]["reason"] == "execution_disabled"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    stored = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_rendered_command_result"
    ]

    assert len(stored) == 1
    assert stored[0]["payload"]["executed"] is False


@pytest.mark.asyncio
async def test_run_rendered_retry_commands_filters_by_rendered_command_id(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command(rendered_command_id="rendered-command-1"))
    await crdt.add_genome(_rendered_command(rendered_command_id="rendered-command-2"))

    results = await run_rendered_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="rendered-retry-command-runner-test",
            rendered_command_id="rendered-command-2",
            plan_id="",
        )
    )

    assert len(results) == 1
    assert results[0]["rendered_command_id"] == "rendered-command-2"