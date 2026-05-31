import pytest

from src.swarms.simulation.replay import (
    build_replay_scenario_from_memory_record,
    build_replay_scenarios_from_memory_records,
)


def _memory_record(status: str = "passed") -> dict:
    return {
        "type": "memory_record",
        "memory_id": "memory-evidence-ev-1",
        "kind": "runtime_evidence",
        "status": status,
        "subject": "runtime_directive_seed_check",
        "source": "evidence-memory-bridge",
        "payload": {
            "evidence_id": "ev-1",
            "directive_id": "runtime-reduce-risk-1",
            "checks": [
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_result_published", "status": "passed"},
                {"name": "directive_applied", "status": "passed"},
            ],
            "evidence_payload": {
                "directive": {
                    "directive_id": "runtime-reduce-risk-1",
                    "action": "REDUCE_RISK",
                    "target_type": "swarm",
                    "target": "trade",
                    "status": "issued",
                },
                "result": {
                    "directive_id": "runtime-reduce-risk-1",
                    "status": "applied",
                    "source": "trade-1",
                    "swarm": "trade",
                },
            },
        },
    }


def test_build_replay_scenario_from_runtime_evidence_memory_record() -> None:
    scenario = build_replay_scenario_from_memory_record(
        _memory_record(),
        source="test-builder",
    )

    assert scenario["type"] == "simulation_replay_scenario"
    assert scenario["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert scenario["source"] == "test-builder"
    assert scenario["status"] == "pending"
    assert scenario["replay_kind"] == "runtime_evidence"
    assert scenario["directive_id"] == "runtime-reduce-risk-1"
    assert scenario["evidence_id"] == "ev-1"
    assert scenario["memory_id"] == "memory-evidence-ev-1"
    assert scenario["action"] == "REDUCE_RISK"
    assert scenario["expected_result_status"] == "applied"
    assert scenario["payload"]["directive"]["action"] == "REDUCE_RISK"
    assert scenario["payload"]["result"]["status"] == "applied"


def test_build_replay_scenario_rejects_non_runtime_evidence_memory() -> None:
    with pytest.raises(ValueError, match="runtime_evidence"):
        build_replay_scenario_from_memory_record(
            {
                "type": "memory_record",
                "memory_id": "mem-1",
                "kind": "note",
                "status": "passed",
                "payload": {},
            }
        )


def test_build_replay_scenario_rejects_failed_runtime_evidence() -> None:
    with pytest.raises(ValueError, match="passed"):
        build_replay_scenario_from_memory_record(_memory_record(status="failed"))


def test_build_replay_scenarios_from_memory_records_skips_non_replayable_records() -> None:
    scenarios = build_replay_scenarios_from_memory_records(
        [
            _memory_record(),
            _memory_record(status="failed"),
            {"type": "memory_record", "kind": "note"},
            "not-a-record",
        ],
        source="test-builder",
    )

    assert len(scenarios) == 1
    assert scenarios[0]["directive_id"] == "runtime-reduce-risk-1"