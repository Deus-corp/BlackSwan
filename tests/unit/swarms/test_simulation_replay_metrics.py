from src.swarms.simulation.replay_metrics import (
    build_simulation_replay_heartbeat_metrics,
    summarize_replay_scenarios,
)


def test_summarize_replay_scenarios_counts_status_kind_and_action() -> None:
    records = [
        {
            "type": "simulation_replay_scenario",
            "scenario_id": "replay-1",
            "status": "pending",
            "replay_kind": "runtime_evidence",
            "action": "REDUCE_RISK",
        },
        {
            "type": "simulation_replay_scenario",
            "scenario_id": "replay-2",
            "status": "completed",
            "replay_kind": "runtime_evidence",
            "action": "REDUCE_RISK",
        },
        {
            "type": "simulation_replay_scenario",
            "scenario_id": "replay-3",
            "status": "failed",
            "replay_kind": "manual",
            "action": "OBSERVE",
        },
        {
            "type": "memory_record",
            "kind": "runtime_evidence",
        },
    ]

    summary = summarize_replay_scenarios(records)

    assert summary["simulation_replay_scenarios"] == 3
    assert summary["simulation_replay_pending"] == 1
    assert summary["simulation_replay_completed"] == 1
    assert summary["simulation_replay_failed"] == 1
    assert summary["simulation_replay_status_counts"] == {
        "pending": 1,
        "completed": 1,
        "failed": 1,
    }
    assert summary["simulation_replay_kind_counts"]["runtime_evidence"] == 2
    assert summary["simulation_replay_kind_counts"]["manual"] == 1
    assert summary["simulation_replay_action_counts"]["REDUCE_RISK"] == 2
    assert summary["simulation_replay_action_counts"]["OBSERVE"] == 1


def test_build_simulation_replay_heartbeat_metrics_returns_zero_counts_for_empty_records() -> None:
    metrics = build_simulation_replay_heartbeat_metrics([])

    assert metrics["simulation_replay_scenarios"] == 0
    assert metrics["simulation_replay_pending"] == 0
    assert metrics["simulation_replay_completed"] == 0
    assert metrics["simulation_replay_failed"] == 0
    assert metrics["simulation_replay_status_counts"] == {}