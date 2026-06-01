import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
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
        visibility={
            "memory_summary": {
                "replay_execution_evidence_records": 1,
            },
            "security_validation": {
                "security_validation_record_type_counts": {
                    "replay_evidence_lifecycle_result": 1,
                }
            },
        },
    )

    assert all(check["status"] == "passed" for check in checks)
    assert any(
        check["name"] == "visibility_memory_summary_replay_evidence"
        and check["status"] == "passed"
        for check in checks
    )
    assert any(
        check["name"] == "visibility_security_lifecycle_validation"
        and check["status"] == "passed"
        for check in checks
    )


@pytest.mark.asyncio
async def test_run_replay_evidence_check_fails_when_execution_missing(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    result = await run_replay_evidence_check(
        argparse.Namespace(
            scenario_id="replay-test-missing-execution",
            action="REDUCE_RISK",
            directive_id="runtime-run-replay-missing-execution",
            source="replay-evidence-check-test",
            expected_result_status="applied",
            wait_seconds=0.01,
            poll_interval=0.01,
            db_path=db_path,
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

    assert result["result_record"]["type"] == "replay_evidence_lifecycle_result"
    assert result["result_record"]["status"] == "failed"
    assert result["result_record"]["payload"]["evidence_count"] == 0
    assert result["result_record"]["payload"]["memory_record_count"] == 0
    assert "visibility" in result
    assert result["result_record"]["payload"]["visibility"]["memory_summary"]["replay_execution_evidence_records"] == 0

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    try:
        refresh = getattr(reader, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(reader, "state", {}) or {}
        results = [
            item
            for item in state.values()
            if isinstance(item, dict)
            and item.get("type") == "replay_evidence_lifecycle_result"
            and item.get("directive_id") == "runtime-run-replay-missing-execution"
        ]
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            close()

    assert len(results) == 1
    assert results[0]["status"] == "failed"
    assert results[0]["payload"]["evidence_count"] == 0
    assert results[0]["payload"]["memory_record_count"] == 0
    assert "visibility" in results[0]["payload"]