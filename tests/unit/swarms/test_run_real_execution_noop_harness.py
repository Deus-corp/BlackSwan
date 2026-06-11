import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_real_execution_noop_harness import (
    REAL_NOOP_RESULT_TYPE,
    build_real_execution_noop_result_record,
    run_real_execution_noop_harness,
)


def _dry_run_envelope(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_dry_run_envelope",
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
        "command": "python -m src.testing.run_replay_evidence_check --scenario-id s --directive-id d --timeout-profile standard",
        "argv": ["python", "-m", "src.testing.run_replay_evidence_check"],
        "cwd": "/workspaces/BlackSwan",
        "env_keys": ["PATH", "PYTHONPATH", "PWD"],
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "dry_run_only": True,
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "real_execution_dry_run_envelope_recorded",
    }
    item.update(overrides)
    return item


def test_build_real_execution_noop_result_record_runs_fixed_noop_only() -> None:
    record = build_real_execution_noop_result_record(_dry_run_envelope())

    assert record["type"] == REAL_NOOP_RESULT_TYPE
    assert record["noop_only"] is True
    assert record["rendered_command_executed"] is False
    assert record["dry_run_envelope_command_executed"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_invoked"] is True
    assert record["execution_performed"] is True
    assert record["exit_code"] == 0
    assert "controlled-noop-ok" in record["stdout"]


@pytest.mark.asyncio
async def test_run_real_execution_noop_harness_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_dry_run_envelope())

    first = await run_real_execution_noop_harness(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-noop-harness-test",
            rendered_command_id="rendered-1",
            real_execution_dry_run_envelope_id="",
            timeout_seconds=5.0,
            json=False,
        )
    )
    second = await run_real_execution_noop_harness(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-noop-harness-test",
            rendered_command_id="rendered-1",
            real_execution_dry_run_envelope_id="",
            timeout_seconds=5.0,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["noop_only"] is True
    assert first[0]["subprocess_invoked"] is True
    assert first[0]["exit_code"] == 0


@pytest.mark.asyncio
async def test_run_real_execution_noop_harness_ignores_non_dry_run_envelope(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_dry_run_envelope(dry_run_only=False))

    results = await run_real_execution_noop_harness(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-noop-harness-test",
            rendered_command_id="rendered-1",
            real_execution_dry_run_envelope_id="",
            timeout_seconds=5.0,
            json=False,
        )
    )

    assert results == []