import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_promotion import (
    ALLOWED_READ_ONLY_MODULE,
    REAL_READ_ONLY_PROMOTION_TYPE,
    build_real_execution_read_only_promotion_record,
    build_real_execution_read_only_promotions,
)


def _noop_result(**overrides):
    payload = {
        "envelope_command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id s --action REDUCE_RISK --directive-id d "
            "--timeout-profile standard"
        ),
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": True,
        "execution_performed": True,
    }
    item = {
        "type": "replay_lifecycle_retry_real_execution_noop_result",
        "real_execution_noop_result_id": "real-noop-result-1",
        "real_execution_dry_run_envelope_id": "real-dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": True,
        "execution_performed": True,
        "exit_code": 0,
        "stdout": "controlled-noop-ok\n",
        "stderr": "",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "payload": payload,
    }
    item.update(overrides)
    return item


def test_build_real_execution_read_only_promotion_promotes_safe_candidate() -> None:
    record = build_real_execution_read_only_promotion_record(_noop_result())

    assert record["type"] == REAL_READ_ONLY_PROMOTION_TYPE
    assert record["promotion_status"] == "promoted"
    assert record["read_only_candidate"] is True
    assert record["read_only_module"] == ALLOWED_READ_ONLY_MODULE
    assert record["command_parse_valid"] is True
    assert record["stdout_marker_observed"] is True
    assert record["noop_exit_code"] == 0
    assert record["rendered_command_executed"] is False
    assert record["dry_run_envelope_command_executed"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False


def test_build_real_execution_read_only_promotion_blocks_non_allowlisted_module() -> None:
    noop = _noop_result()
    noop["payload"]["envelope_command"] = "python -m os --help"

    record = build_real_execution_read_only_promotion_record(noop)

    assert record["promotion_status"] == "blocked"
    assert record["read_only_candidate"] is False
    assert "read_only_module_not_allowlisted" in record["reasons"]


def test_build_real_execution_read_only_promotion_blocks_missing_noop_marker() -> None:
    record = build_real_execution_read_only_promotion_record(
        _noop_result(stdout="")
    )

    assert record["promotion_status"] == "blocked"
    assert "noop_stdout_marker_missing" in record["reasons"]


@pytest.mark.asyncio
async def test_build_real_execution_read_only_promotions_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_noop_result())

    first = await build_real_execution_read_only_promotions(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-promotion-test",
            rendered_command_id="rendered-1",
            real_execution_noop_result_id="",
            json=False,
        )
    )
    second = await build_real_execution_read_only_promotions(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-promotion-test",
            rendered_command_id="rendered-1",
            real_execution_noop_result_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["promotion_status"] == "promoted"