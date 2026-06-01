import argparse

import pytest

from src.testing.run_replay_evidence_check import _build_checks, run_replay_evidence_check


def test_build_checks_passes_for_complete_chain() -> None:
    checks = _build_checks(
        scenario={
            "type": "simulation_replay_scenario",
            "scenario_id": "replay-1",
        },
        directive={
            "type": "swarm_directive",
            "directive_id": "run-replay-1",
        },
        execution={
            "type": "simulation_replay_execution",
            "status": "completed",
        },
        evidence_records=[
            {
                "type": "evidence_record",
                "status": "passed",
            }
        ],
        memory_records=[
            {
                "type": "memory_record",
                "kind": "runtime_evidence",
            }
        ],
    )

    assert all(check["status"] == "passed" for check in checks)


@pytest.mark.asyncio
async def test_run_replay_evidence_check_fails_when_execution_missing(tmp_path) -> None:
    result = await run_replay_evidence_check(
        argparse.Namespace(
            scenario_id="replay-test-missing-execution",
            action="REDUCE_RISK",
            directive_id="runtime-run-replay-missing-execution",
            source="replay-evidence-check-test",
            expected_result_status="applied",
            wait_seconds=0.01,
            poll_interval=0.01,
            db_path=str(tmp_path / "crdt.db"),
        )
    )

    assert result["status"] == "failed"
    assert result["scenario"]["type"] == "simulation_replay_scenario"
    assert result["directive"]["type"] == "swarm_directive"
    assert result["execution"] is None
    assert any(
        check["name"] == "execution_published" and check["status"] == "failed"
        for check in result["checks"]
    )