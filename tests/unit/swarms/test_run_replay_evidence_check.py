import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_replay_evidence_check import (
    _build_checks,
    async_main,
    main,
    run_replay_evidence_check,
)


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
            "trail_counts": {
                "simulation_replay_scenario": 1,
                "swarm_directive": 1,
                "simulation_replay_execution": 1,
                "evidence_record": 1,
                "memory_record": 1,
                "replay_evidence_lifecycle_result": 1,
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
    assert any(
        check["name"] == "visibility_crdt_trail_complete"
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

    assert any(
        check["name"] == "execution_published" and check["status"] == "failed"
        for check in result["checks"]
    )
    assert any(
        check["name"] == "visibility_crdt_trail_complete"
        and check["status"] == "failed"
        for check in result["checks"]
    )

    assert result["result_record"]["type"] == "replay_evidence_lifecycle_result"
    assert result["result_record"]["status"] == "failed"
    assert result["result_record"]["payload"]["evidence_count"] == 0
    assert result["result_record"]["payload"]["memory_record_count"] == 0
    assert "visibility" in result
    assert (
        result["result_record"]["payload"]["visibility"]["memory_summary"][
            "replay_execution_evidence_records"
        ]
        == 0
    )
    assert "trail_counts" in result["visibility"]
    assert (
        result["result_record"]["payload"]["visibility"]["trail_counts"][
            "simulation_replay_execution"
        ]
        == 0
    )
    assert (
        result["result_record"]["payload"]["failure_reason"]
        == "execution_not_observed_before_timeout"
    )
    assert result["result_record"]["payload"]["wait_seconds"] == 0.01
    assert result["result_record"]["payload"]["poll_interval"] == 0.01

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
    assert "trail_counts" in results[0]["payload"]["visibility"]
    assert (
        results[0]["payload"]["visibility"]["trail_counts"][
            "simulation_replay_execution"
        ]
        == 0
    )
    assert (
        results[0]["payload"]["failure_reason"]
        == "execution_not_observed_before_timeout"
    )
    assert results[0]["payload"]["wait_seconds"] == 0.01
    assert results[0]["payload"]["poll_interval"] == 0.01


@pytest.mark.asyncio
async def test_async_main_returns_zero_when_lifecycle_check_passes(monkeypatch) -> None:
    async def fake_run_replay_evidence_check(_args):
        return {
            "status": "passed",
            "scenario_id": "replay-test",
            "directive_id": "directive-test",
            "checks": [
                {
                    "name": "scenario_seeded",
                    "status": "passed",
                    "value": "replay-test",
                }
            ],
        }

    monkeypatch.setattr(
        "src.testing.run_replay_evidence_check.run_replay_evidence_check",
        fake_run_replay_evidence_check,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["run_replay_evidence_check"],
    )

    assert await async_main() == 0


@pytest.mark.asyncio
async def test_async_main_returns_nonzero_when_lifecycle_check_fails(monkeypatch) -> None:
    async def fake_run_replay_evidence_check(_args):
        return {
            "status": "failed",
            "scenario_id": "replay-test",
            "directive_id": "directive-test",
            "checks": [
                {
                    "name": "execution_published",
                    "status": "failed",
                    "value": None,
                }
            ],
        }

    monkeypatch.setattr(
        "src.testing.run_replay_evidence_check.run_replay_evidence_check",
        fake_run_replay_evidence_check,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["run_replay_evidence_check"],
    )

    assert await async_main() == 1


def test_main_exits_with_async_main_code(monkeypatch) -> None:
    async def fake_async_main() -> int:
        return 1

    monkeypatch.setattr(
        "src.testing.run_replay_evidence_check.async_main",
        fake_async_main,
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1