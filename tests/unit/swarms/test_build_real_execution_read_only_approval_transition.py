import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.build_real_execution_read_only_approval_transition import (
    REAL_READ_ONLY_APPROVAL_TRANSITION_TYPE,
    build_real_execution_read_only_approval_transition_record,
    build_real_execution_read_only_approval_transitions,
)


def _approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_approval",
        "real_execution_read_only_approval_id": "read-only-approval-1",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-result-1",
        "real_execution_dry_run_envelope_id": "dry-run-envelope-1",
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
        "approval_status": "pending",
        "read_only_command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id s --directive-id d --timeout-profile standard"
        ),
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
        ],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_explicit_approval_required",
    }
    item.update(overrides)
    return item


def test_build_real_execution_read_only_approval_transition_approves_but_stays_disabled() -> None:
    record = build_real_execution_read_only_approval_transition_record(
        _approval(),
        to_status="approved",
    )

    assert record["type"] == REAL_READ_ONLY_APPROVAL_TRANSITION_TYPE
    assert record["from_status"] == "pending"
    assert record["to_status"] == "approved"
    assert record["read_only_execution_enabled"] is False
    assert record["real_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["subprocess_invoked"] is False
    assert record["execution_performed"] is False
    assert record["rendered_command_executed"] is False
    assert record["dry_run_envelope_command_executed"] is False
    assert record["reason"] == "read_only_execution_approval_transition_recorded"


def test_build_real_execution_read_only_approval_transition_rejects_but_stays_disabled() -> None:
    record = build_real_execution_read_only_approval_transition_record(
        _approval(),
        to_status="rejected",
    )

    assert record["from_status"] == "pending"
    assert record["to_status"] == "rejected"
    assert record["read_only_execution_enabled"] is False
    assert record["subprocess_enabled"] is False
    assert record["execution_performed"] is False


def test_build_real_execution_read_only_approval_transition_rejects_bad_target_status() -> None:
    with pytest.raises(ValueError, match="unsupported to_status"):
        build_real_execution_read_only_approval_transition_record(
            _approval(),
            to_status="enabled",
        )


def test_build_real_execution_read_only_approval_transition_rejects_non_pending_source() -> None:
    with pytest.raises(ValueError, match="requires pending source"):
        build_real_execution_read_only_approval_transition_record(
            _approval(approval_status="approved"),
            to_status="approved",
        )


@pytest.mark.asyncio
async def test_build_real_execution_read_only_approval_transitions_publishes_once(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_approval())

    first = await build_real_execution_read_only_approval_transitions(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-approval-transition-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_approval_id="",
            to_status="approved",
            json=False,
        )
    )
    second = await build_real_execution_read_only_approval_transitions(
        argparse.Namespace(
            db_path=db_path,
            source="real-execution-read-only-approval-transition-test",
            rendered_command_id="rendered-1",
            real_execution_read_only_approval_id="",
            to_status="approved",
            json=False,
        )
    )

    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["from_status"] == "pending"
    assert first[0]["to_status"] == "approved"
    assert first[0]["read_only_execution_enabled"] is False