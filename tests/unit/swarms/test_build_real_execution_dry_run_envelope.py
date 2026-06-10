import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_dry_run_envelope import (
    REAL_DRY_RUN_ENVELOPE_TYPE,
    build_real_execution_dry_run_envelope_record,
    build_real_execution_dry_run_envelopes,
)


def _final_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_final_gate",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "gate_status": "blocked",
        "would_execute": False,
        "ready_for_real_execution": False,
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


def test_build_real_execution_dry_run_envelope_record_captures_envelope_without_execution() -> None:
    record = build_real_execution_dry_run_envelope_record(_final_gate())

    assert record["type"] == REAL_DRY_RUN_ENVELOPE_TYPE
    assert record["dry_run_only"] is True
    assert record["would_execute"] is False
    assert record["ready_for_real_execution"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False
    assert record["subprocess_invoked"] is False
    assert record["argv"][:3] == ["python", "-m", "src.testing.run_replay_evidence_check"]
    assert isinstance(record["cwd"], str)
    assert isinstance(record["env_keys"], list)


def test_build_real_execution_dry_run_envelope_record_requires_command() -> None:
    with pytest.raises(ValueError, match="command is required"):
        build_real_execution_dry_run_envelope_record(_final_gate(command=""))


@pytest.mark.asyncio
async def test_build_real_execution_dry_run_envelopes_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_final_gate())

    first = await build_real_execution_dry_run_envelopes(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-dry-run-envelope-test",
            rendered_command_id="rendered-1",
            real_execution_final_gate_id="",
            json=False,
        )
    )
    second = await build_real_execution_dry_run_envelopes(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-dry-run-envelope-test",
            rendered_command_id="rendered-1",
            real_execution_final_gate_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["dry_run_only"] is True
    assert first[0]["subprocess_invoked"] is False