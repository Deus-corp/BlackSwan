import pytest

from src.swarms.simulation.replay_executor import (
    execute_replay_dry_run,
    execute_replay_dry_run_from_records,
    find_replay_scenario,
)


def _scenario() -> dict:
    return {
        "type": "simulation_replay_scenario",
        "scenario_id": "replay-runtime-reduce-risk-1",
        "status": "pending",
        "replay_kind": "runtime_evidence",
        "directive_id": "runtime-reduce-risk-1",
        "action": "REDUCE_RISK",
        "expected_result_status": "applied",
        "payload": {},
    }


def _directive() -> dict:
    return {
        "type": "swarm_directive",
        "directive_id": "run-replay-1",
        "action": "RUN_REPLAY",
        "target_type": "swarm",
        "target": "simulation",
        "payload": {
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": True,
        },
    }


def test_find_replay_scenario_by_id() -> None:
    assert find_replay_scenario([_scenario()], "replay-runtime-reduce-risk-1") == _scenario()
    assert find_replay_scenario([_scenario()], "missing") is None


def test_execute_replay_dry_run_returns_completed_receipt() -> None:
    receipt = execute_replay_dry_run(
        scenario=_scenario(),
        directive=_directive(),
        source="simulation-test",
    )

    assert receipt["type"] == "simulation_replay_execution"
    assert receipt["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert receipt["directive_id"] == "run-replay-1"
    assert receipt["source"] == "simulation-test"
    assert receipt["status"] == "completed"
    assert receipt["dry_run"] is True
    assert receipt["action"] == "REDUCE_RISK"
    assert receipt["expected_result_status"] == "applied"
    assert receipt["checks"][0]["name"] == "scenario_found"


def test_execute_replay_dry_run_rejects_non_dry_run_directive() -> None:
    directive = _directive()
    directive["payload"]["dry_run"] = False

    with pytest.raises(ValueError, match="dry_run"):
        execute_replay_dry_run(
            scenario=_scenario(),
            directive=directive,
        )


def test_execute_replay_dry_run_from_records_fails_when_scenario_missing() -> None:
    with pytest.raises(ValueError, match="not found"):
        execute_replay_dry_run_from_records(
            records=[],
            directive=_directive(),
        )


def test_execute_replay_dry_run_from_records_finds_and_executes() -> None:
    receipt = execute_replay_dry_run_from_records(
        records=[_scenario()],
        directive=_directive(),
        source="simulation-test",
    )

    assert receipt["status"] == "completed"
    assert receipt["scenario_id"] == "replay-runtime-reduce-risk-1"