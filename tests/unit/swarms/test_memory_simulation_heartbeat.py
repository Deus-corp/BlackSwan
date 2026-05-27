from src.swarms.memory.heartbeat import build_memory_heartbeat
from src.swarms.simulation.heartbeat import build_simulation_heartbeat


def test_memory_heartbeat_is_canonical_swarm_heartbeat() -> None:
    payload = build_memory_heartbeat(
        "memory-test",
        metrics={"records": 3},
        details={"mode": "test"},
    )

    assert payload["type"] == "swarm_heartbeat"
    assert payload["swarm"] == "memory"
    assert payload["node_id"] == "memory-test"
    assert payload["role"] == "node"
    assert payload["status"] == "running"
    assert "episodic_memory" in payload["capabilities"]
    assert payload["metrics"]["records"] == 3
    assert payload["details"]["mode"] == "test"


def test_simulation_heartbeat_is_canonical_swarm_heartbeat() -> None:
    payload = build_simulation_heartbeat(
        "simulation-test",
        metrics={"scenarios_run": 1},
        details={"mode": "test"},
    )

    assert payload["type"] == "swarm_heartbeat"
    assert payload["swarm"] == "simulation"
    assert payload["node_id"] == "simulation-test"
    assert payload["role"] == "node"
    assert payload["status"] == "running"
    assert "scenario_run" in payload["capabilities"]
    assert payload["metrics"]["scenarios_run"] == 1
    assert payload["details"]["mode"] == "test"