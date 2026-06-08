import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_controlled_retry_command import (
    CONTROLLED_RESULT_TYPE,
    build_controlled_retry_command_result,
    run_controlled_retry_commands,
)


def _rendered_command(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-controlled-test "
        "--directive-id runtime-run-replay-controlled-test "
        "--timeout-profile standard"
    )
    item = {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": "rendered-controlled-1",
        "plan_id": "plan-controlled-1",
        "proposal_id": "proposal-controlled-1",
        "approval_id": "approval-controlled-1",
        "status": "rendered",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
            "rendered_command_id": "rendered-controlled-1",
            "plan_id": "plan-controlled-1",
            "proposal_id": "proposal-controlled-1",
            "approval_id": "approval-controlled-1",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command": command,
            "execution_enabled": False,
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def test_build_controlled_retry_command_result_rejects_by_default() -> None:
    result = build_controlled_retry_command_result(_rendered_command())

    assert result["type"] == CONTROLLED_RESULT_TYPE
    assert result["controlled_execution_result_id"].startswith(
        "replay-retry-controlled-result-"
    )
    assert result["rendered_command_id"] == "rendered-controlled-1"
    assert result["status"] == "rejected"
    assert result["reason"] == "controlled_execution_not_implemented"
    assert result["execution_enabled"] is False
    assert result["operator_authorized"] is False
    assert result["allowlist_matched"] is True
    assert result["command_parse"]["valid"] is True
    assert result["command_parse"]["allowlist_matched"] is True
    assert result["readiness_score"] == 0
    assert result["payload"]["allowlist_matched"] is True
    assert result["payload"]["command_parse"]["valid"] is True
    assert result["mock_execution"]["status"] == "blocked"
    assert result["mock_execution"]["mock_execution"]["performed"] is False
    assert result["mock_execution"]["mock_execution"]["subprocess_invoked"] is False
    assert result["payload"]["mock_execution"]["payload"]["executed"] is False


def test_build_controlled_retry_command_result_rejects_even_when_execution_enabled() -> None:
    result = build_controlled_retry_command_result(
        _rendered_command(execution_enabled=True)
    )

    assert result["status"] == "rejected"
    assert result["reason"] == "controlled_execution_not_implemented"
    assert result["execution_enabled"] is True
    assert result["operator_authorized"] is False
    assert result["allowlist_matched"] is True
    assert result["payload"]["executed"] is False


def test_build_controlled_retry_command_result_requires_rendered_command_id() -> None:
    with pytest.raises(ValueError, match="rendered_command_id"):
        build_controlled_retry_command_result(
            _rendered_command(rendered_command_id="")
        )


@pytest.mark.asyncio
async def test_run_controlled_retry_commands_publishes_rejected_result(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    results = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=False,
            mock_execution=False,
        )
    )

    assert len(results) == 1
    assert results[0]["type"] == CONTROLLED_RESULT_TYPE
    assert results[0]["status"] == "rejected"
    assert results[0]["reason"] == "controlled_execution_not_implemented"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    stored = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == CONTROLLED_RESULT_TYPE
        and item.get("rendered_command_id") == "rendered-controlled-1"
    ]

    assert len(stored) == 1
    assert stored[0]["payload"]["executed"] is False


@pytest.mark.asyncio
async def test_run_controlled_retry_commands_skips_duplicate_for_rendered_command(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    first = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=False,
            mock_execution=False,
        )
    )
    second = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=False,
            mock_execution=False,
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
        and item.get("type") == CONTROLLED_RESULT_TYPE
        and item.get("rendered_command_id") == "rendered-controlled-1"
    ]

    assert len(stored) == 1
    assert stored[0]["status"] == "rejected"


def test_build_controlled_retry_command_result_records_operator_authorization_intent() -> None:
    result = build_controlled_retry_command_result(
        _rendered_command(),
        operator_authorized=True,
    )

    assert result["status"] == "rejected"
    assert result["reason"] == "controlled_execution_not_implemented"
    assert result["operator_authorized"] is True
    assert result["payload"]["operator_authorized"] is True
    assert result["payload"]["executed"] is False
    assert result["mock_execution"]["status"] == "blocked"
    assert result["mock_execution"]["mock_execution"]["performed"] is False
    assert (
        "mock_execution_not_enabled"
        in result["mock_execution"]["mock_execution"]["reasons"]
    )


@pytest.mark.asyncio
async def test_run_controlled_retry_commands_records_operator_authorization_flag(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    results = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=True,
            mock_execution=False,
        )
    )

    assert len(results) == 1
    assert results[0]["status"] == "rejected"
    assert results[0]["reason"] == "controlled_execution_not_implemented"
    assert results[0]["operator_authorized"] is True
    assert results[0]["payload"]["operator_authorized"] is True
    assert results[0]["payload"]["executed"] is False


def test_build_controlled_retry_command_result_attaches_mock_execution_envelope() -> None:
    result = build_controlled_retry_command_result(
        _rendered_command(),
        operator_authorized=True,
        mock_execution_enabled=True,
    )

    assert result["status"] == "rejected"
    assert result["reason"] == "controlled_execution_not_implemented"
    assert result["payload"]["executed"] is False
    assert result["mock_execution"]["status"] == "mock_executed"
    assert result["mock_execution"]["mock_execution"]["performed"] is True
    assert result["mock_execution"]["mock_execution"]["subprocess_invoked"] is False
    assert result["payload"]["mock_execution"]["payload"]["mock_executed"] is True


@pytest.mark.asyncio
async def test_run_controlled_retry_commands_records_mock_execution_envelope(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    results = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=True,
            mock_execution=True,
        )
    )

    assert len(results) == 1
    assert results[0]["status"] == "rejected"
    assert results[0]["payload"]["executed"] is False
    assert results[0]["mock_execution"]["status"] == "mock_executed"
    assert results[0]["mock_execution"]["mock_execution"]["performed"] is True
    assert (
        results[0]["mock_execution"]["mock_execution"]["subprocess_invoked"]
        is False
    )

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    summaries = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_mock_execution_summary"
        and item.get("rendered_command_id") == "rendered-controlled-1"
    ]

    assert len(summaries) == 1
    assert summaries[0]["status"] == "mock_executed"
    assert summaries[0]["mock_performed"] is True
    assert summaries[0]["subprocess_invoked"] is False
    assert summaries[0]["payload"]["executed"] is False


@pytest.mark.asyncio
async def test_run_controlled_retry_commands_does_not_duplicate_mock_summary(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    first = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=True,
            mock_execution=True,
        )
    )
    second = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=True,
            mock_execution=True,
        )
    )

    assert len(first) == 1
    assert len(second) == 0

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    controlled_results = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == CONTROLLED_RESULT_TYPE
        and item.get("rendered_command_id") == "rendered-controlled-1"
    ]
    summaries = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_mock_execution_summary"
        and item.get("rendered_command_id") == "rendered-controlled-1"
    ]

    assert len(controlled_results) == 1
    assert len(summaries) == 1
    assert summaries[0]["controlled_execution_result_id"] == controlled_results[0][
        "controlled_execution_result_id"
    ]
    assert summaries[0]["status"] == "mock_executed"
    assert summaries[0]["subprocess_invoked"] is False


@pytest.mark.asyncio
async def test_run_controlled_retry_commands_does_not_publish_mock_summary_without_mock_flag(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_rendered_command())

    results = await run_controlled_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-retry-command-runner-test",
            rendered_command_id="rendered-controlled-1",
            plan_id="",
            json=False,
            allow_controlled_execution=True,
            mock_execution=False,
        )
    )

    assert len(results) == 1

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    summaries = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_mock_execution_summary"
    ]

    assert summaries == []