import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_controlled_mock_execution_summary import (
    MOCK_SUMMARY_TYPE,
    build_controlled_mock_execution_summaries,
    build_controlled_mock_execution_summary,
)


def _controlled_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "proposal_id": "proposal-1",
        "plan_id": "plan-1",
        "approval_id": "approval-1",
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "payload": {
            "executed": False,
        },
        "mock_execution": {
            "type": "controlled_retry_mock_execution",
            "status": "mock_executed",
            "reason": "mock_execution_completed",
            "mock_execution_enabled": True,
            "real_execution_enabled": False,
            "mock_execution": {
                "performed": True,
                "adapter": "mock",
                "subprocess_invoked": False,
                "exit_code": 0,
                "stdout": "mock controlled retry execution",
                "stderr": "",
                "reasons": [],
            },
            "payload": {
                "executed": False,
                "mock_executed": True,
                "subprocess_invoked": False,
            },
        },
    }
    item.update(overrides)
    return item


def test_build_controlled_mock_execution_summary_for_mock_executed_result() -> None:
    result = build_controlled_mock_execution_summary(_controlled_result())

    assert result["type"] == MOCK_SUMMARY_TYPE
    assert result["mock_execution_summary_id"].startswith(
        "replay-retry-mock-summary-"
    )
    assert result["controlled_execution_result_id"] == "controlled-result-1"
    assert result["source_controlled_execution_result_id"] == "controlled-result-1"
    assert result["rendered_command_id"] == "rendered-1"
    assert result["status"] == "mock_executed"
    assert result["reason"] == "mock_execution_completed"
    assert result["mock_status"] == "mock_executed"
    assert result["mock_performed"] is True
    assert result["subprocess_invoked"] is False
    assert result["real_execution_enabled"] is False
    assert result["payload"]["executed"] is False
    assert result["payload"]["derived"] is True


def test_build_controlled_mock_execution_summary_blocks_without_mock_performed() -> None:
    controlled = _controlled_result()
    controlled["mock_execution"]["status"] = "blocked"
    controlled["mock_execution"]["reason"] = "mock_execution_blocked"
    controlled["mock_execution"]["mock_execution"]["performed"] = False

    result = build_controlled_mock_execution_summary(controlled)

    assert result["status"] == "blocked"
    assert result["reason"] == "mock_execution_not_observed"
    assert result["mock_performed"] is False
    assert result["subprocess_invoked"] is False


def test_build_controlled_mock_execution_summary_requires_controlled_result_id() -> None:
    with pytest.raises(ValueError, match="controlled_execution_result_id"):
        build_controlled_mock_execution_summary(
            _controlled_result(controlled_execution_result_id="")
        )


@pytest.mark.asyncio
async def test_build_controlled_mock_execution_summaries_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_controlled_result())

    first = await build_controlled_mock_execution_summaries(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-mock-summary-test",
            controlled_execution_result_id="controlled-result-1",
            rendered_command_id="",
            proposal_id="",
            json=False,
        )
    )
    second = await build_controlled_mock_execution_summaries(
        argparse.Namespace(
            db_path=db_path,
            source="controlled-mock-summary-test",
            controlled_execution_result_id="controlled-result-1",
            rendered_command_id="",
            proposal_id="",
            json=False,
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
        and item.get("type") == MOCK_SUMMARY_TYPE
        and item.get("controlled_execution_result_id") == "controlled-result-1"
    ]

    assert len(stored) == 1
    assert stored[0]["status"] == "mock_executed"
    assert stored[0]["mock_performed"] is True
    assert stored[0]["subprocess_invoked"] is False