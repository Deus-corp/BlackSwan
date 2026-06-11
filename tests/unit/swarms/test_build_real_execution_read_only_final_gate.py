import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_final_gate import (
    REAL_READ_ONLY_FINAL_GATE_TYPE,
    build_real_execution_read_only_final_gate_record,
    build_real_execution_read_only_final_gates,
)


def _promotion(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_promotion",
        "real_execution_read_only_promotion_id": "real-read-only-promotion-1",
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
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "promotion_status": "promoted",
        "read_only_candidate": True,
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id s --action REDUCE_RISK --directive-id d "
            "--timeout-profile standard"
        ),
        "read_only_argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
            "--scenario-id",
            "s",
            "--action",
            "REDUCE_RISK",
            "--directive-id",
            "d",
            "--timeout-profile",
            "standard",
        ],
        "command_parse_valid": True,
        "stdout_marker_observed": True,
        "noop_exit_code": 0,
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
    }
    item.update(overrides)
    return item


def test_build_real_execution_read_only_final_gate_blocks_even_after_safe_promotion() -> None:
    record = build_real_execution_read_only_final_gate_record(_promotion())

    assert record["type"] == REAL_READ_ONLY_FINAL_GATE_TYPE
    assert record["promotion_preconditions_satisfied"] is True
    assert record["gate_status"] == "blocked"
    assert record["ready_for_read_only_execution"] is False
    assert record["would_execute"] is False
    assert record["read_only_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["rendered_command_executed"] is False
    assert record["dry_run_envelope_command_executed"] is False
    assert record["reason"] == "read_only_execution_requires_separate_pr"
    assert "read_only_execution_requires_separate_pr" in record["blocking_reasons"]


def test_build_real_execution_read_only_final_gate_records_failed_preconditions() -> None:
    record = build_real_execution_read_only_final_gate_record(
        _promotion(promotion_status="blocked", read_only_candidate=False)
    )

    assert record["promotion_preconditions_satisfied"] is False
    assert record["gate_status"] == "blocked"
    assert "read_only_promotion_not_promoted" in record["precondition_failures"]
    assert "read_only_candidate_not_observed" in record["precondition_failures"]
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False


def test_build_real_execution_read_only_final_gate_requires_promotion_id() -> None:
    with pytest.raises(
        ValueError,
        match="real_execution_read_only_promotion_id is required",
    ):
        build_real_execution_read_only_final_gate_record(
            _promotion(real_execution_read_only_promotion_id="")
        )


@pytest.mark.asyncio
async def test_build_real_execution_read_only_final_gates_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_promotion())

    first = await build_real_execution_read_only_final_gates(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-final-gate-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_promotion_id="",
            json=False,
        )
    )
    second = await build_real_execution_read_only_final_gates(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-final-gate-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_promotion_id="",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["gate_status"] == "blocked"
    assert first[0]["promotion_preconditions_satisfied"] is True
    assert first[0]["subprocess_invoked"] is False
    assert first[0]["execution_performed"] is False