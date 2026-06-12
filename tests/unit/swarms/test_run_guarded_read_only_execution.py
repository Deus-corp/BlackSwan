import argparse
import subprocess

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_guarded_read_only_execution import (
    ALLOWLISTED_MODULE,
    READ_ONLY_EXECUTION_RESULT_TYPE,
    run_guarded_read_only_execution_from_gate,
    run_guarded_read_only_executions,
)


def _gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_readiness_gate",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "real_execution_read_only_approval_transition_id": "transition-1",
        "real_execution_read_only_approval_id": "approval-1",
        "real_execution_read_only_final_gate_id": "final-gate-1",
        "real_execution_read_only_promotion_id": "promotion-1",
        "real_execution_noop_result_id": "noop-1",
        "real_execution_dry_run_envelope_id": "envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "gate_status": "ready_blocked",
        "read_only_approval_from_status": "pending",
        "read_only_approval_latest_status": "approved",
        "read_only_readiness_satisfied": True,
        "ready_for_guarded_read_only_execution": True,
        "read_only_command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id s --action REDUCE_RISK --directive-id d "
            "--timeout-profile standard --db-path db.sqlite"
        ),
        "read_only_module": ALLOWLISTED_MODULE,
        "read_only_argv": [
            "python",
            "-m",
            ALLOWLISTED_MODULE,
            "--scenario-id",
            "s",
            "--action",
            "REDUCE_RISK",
            "--directive-id",
            "d",
            "--timeout-profile",
            "standard",
            "--db-path",
            "db.sqlite",
        ],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
    }
    item.update(overrides)
    return item


def test_guarded_read_only_execution_rejects_without_explicit_flag() -> None:
    result = run_guarded_read_only_execution_from_gate(
        _gate(),
        operator_authorized=True,
        allow_guarded_read_only_execution=False,
        timeout_seconds=1.0,
    )

    assert result["type"] == READ_ONLY_EXECUTION_RESULT_TYPE
    assert result["status"] == "rejected"
    assert "guarded_read_only_execution_flag_required" in result["validation_reasons"]
    assert result["subprocess_invoked"] is False
    assert result["execution_performed"] is False


def test_guarded_read_only_execution_rejects_non_allowlisted_module() -> None:
    result = run_guarded_read_only_execution_from_gate(
        _gate(
            read_only_module="os",
            read_only_argv=["python", "-m", "os"],
        ),
        operator_authorized=True,
        allow_guarded_read_only_execution=True,
        timeout_seconds=1.0,
    )

    assert result["status"] == "rejected"
    assert "read_only_module_not_allowlisted" in result["validation_reasons"]
    assert result["subprocess_invoked"] is False


def test_guarded_read_only_execution_runs_allowlisted_command(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="read-only-ok\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_guarded_read_only_execution_from_gate(
        _gate(),
        operator_authorized=True,
        allow_guarded_read_only_execution=True,
        timeout_seconds=1.0,
    )

    assert result["status"] == "executed"
    assert result["reason"] == "guarded_read_only_execution_completed"
    assert result["exit_code"] == 0
    assert result["subprocess_invoked"] is True
    assert result["execution_performed"] is True
    assert result["read_only_command_executed"] is True
    assert result["rendered_command_executed"] is True
    assert result["dry_run_envelope_command_executed"] is True
    assert result["stdout"] == "read-only-ok\n"
    assert calls
    assert calls[0][1]["shell"] is False
    assert calls[0][0][0][1:3] == ["-m", ALLOWLISTED_MODULE]


@pytest.mark.asyncio
async def test_guarded_read_only_execution_publishes_once(tmp_path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="read-only-ok\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_gate())

    first = await run_guarded_read_only_executions(
        argparse.Namespace(
            db_path=db_path,
            source="guarded-read-only-execution-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_readiness_gate_id="",
            timeout_seconds=1.0,
            operator_authorized=True,
            allow_guarded_read_only_execution=True,
            json=False,
        )
    )
    second = await run_guarded_read_only_executions(
        argparse.Namespace(
            db_path=db_path,
            source="guarded-read-only-execution-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_readiness_gate_id="",
            timeout_seconds=1.0,
            operator_authorized=True,
            allow_guarded_read_only_execution=True,
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["status"] == "executed"
    assert first[0]["subprocess_invoked"] is True