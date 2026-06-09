import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_preflight import (
    REAL_PREFLIGHT_TYPE,
    build_real_execution_preflight_record,
    build_real_execution_preflights,
)


def _controlled_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rejected",
        "reason": "real_execution_not_supported",
        "operator_authorized": True,
        "allowlist_matched": True,
        "real_execution_requested": True,
        "real_execution_performed": False,
        "real_execution_supported": False,
        "subprocess_invoked": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id replay-controlled-test "
            "--directive-id runtime-run-replay-controlled-test "
            "--timeout-profile standard"
        ),
    }
    item.update(overrides)
    return item


def test_build_real_execution_preflight_record_blocks_without_execution() -> None:
    record = build_real_execution_preflight_record(_controlled_result())

    assert record["type"] == REAL_PREFLIGHT_TYPE
    assert record["status"] == "blocked"
    assert record["reason"] in {
        "real_execution_not_supported",
        "subprocess_not_supported",
        "real_adapter_not_runnable",
        "real_adapter_requires_explicit_pr",
    }
    assert record["real_execution_requested"] is True
    assert record["would_execute"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["real_execution_supported"] is False
    assert record["subprocess_supported"] is False
    assert record["real_adapter_runnable"] is False
    assert record["real_adapter_requires_explicit_pr"] is True
    assert record["payload"]["execution_performed"] is False
    assert record["payload"]["subprocess_invoked"] is False


def test_build_real_execution_preflight_record_requires_controlled_result_id() -> None:
    with pytest.raises(ValueError, match="controlled_execution_result_id"):
        build_real_execution_preflight_record(
            _controlled_result(controlled_execution_result_id="")
        )


@pytest.mark.asyncio
async def test_build_real_execution_preflights_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_controlled_result())

    first = await build_real_execution_preflights(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-preflight-test",
            rendered_command_id="rendered-1",
            controlled_execution_result_id="",
            require_real_execution_request=True,
            json=False,
        )
    )
    second = await build_real_execution_preflights(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-preflight-test",
            rendered_command_id="rendered-1",
            controlled_execution_result_id="",
            require_real_execution_request=True,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["status"] == "blocked"
    assert first[0]["execution_performed"] is False
    assert first[0]["subprocess_invoked"] is False