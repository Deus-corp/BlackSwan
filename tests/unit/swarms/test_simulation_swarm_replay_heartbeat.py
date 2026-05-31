import pytest
import asyncio

from src.swarms.simulation.node import SimulationSwarmNode


class DummyCRDT:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.state = {
            "scenario": {
                "type": "simulation_replay_scenario",
                "scenario_id": "replay-runtime-reduce-risk-1",
                "status": "pending",
                "replay_kind": "runtime_evidence",
                "action": "REDUCE_RISK",
            },
            "execution": {
                "type": "simulation_replay_execution",
                "execution_id": "exec-replay-runtime-reduce-risk-1",
                "scenario_id": "replay-runtime-reduce-risk-1",
                "status": "completed",
            },
        }
        self.payloads = []

    def refresh_from_storage(self) -> int:
        self.refresh_calls += 1
        return len(self.state)

    async def add_genome(self, payload):
        self.payloads.append(payload)


def make_node() -> SimulationSwarmNode:
    try:
        return SimulationSwarmNode(node_id="simulation-test")
    except TypeError:
        node = SimulationSwarmNode()
        node.node_id = "simulation-test"
        return node


@pytest.mark.asyncio
async def test_simulation_swarm_heartbeat_reports_replay_scenario_metrics() -> None:
    node = make_node()
    node.crdt = DummyCRDT()

    await node.publish_heartbeat()

    assert node.crdt.refresh_calls == 1

    heartbeat = node.crdt.payloads[-1]
    metrics = heartbeat["metrics"]

    assert metrics["simulation_replay_metrics_enabled"] is True

    assert metrics["simulation_replay_scenarios"] == 1
    assert metrics["simulation_replay_pending"] == 1
    assert metrics["simulation_replay_completed"] == 0
    assert metrics["simulation_replay_failed"] == 0
    assert metrics["simulation_replay_status_counts"] == {"pending": 1}
    assert metrics["simulation_replay_action_counts"]["REDUCE_RISK"] == 1

    assert metrics["simulation_replay_executions"] == 1
    assert metrics["simulation_replay_execution_completed"] == 1
    assert metrics["simulation_replay_execution_failed"] == 0
    assert metrics["simulation_replay_execution_status_counts"] == {"completed": 1}

@pytest.mark.asyncio
async def test_simulation_heartbeat_loop_publishes_once(monkeypatch) -> None:
    node = make_node()
    node.crdt = DummyCRDT()

    async def fake_sleep(_seconds: float) -> None:
        node.shutdown_event.set()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await node._heartbeat_loop()

    assert node.crdt.payloads
    assert node.crdt.payloads[-1]["type"] == "swarm_heartbeat"
    