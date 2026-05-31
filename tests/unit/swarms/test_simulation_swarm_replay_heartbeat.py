import pytest

from src.swarms.simulation.node import SimulationSwarmNode


class DummyCRDT:
    def __init__(self) -> None:
        self.state = {
            "scenario": {
                "type": "simulation_replay_scenario",
                "scenario_id": "replay-runtime-reduce-risk-1",
                "status": "pending",
                "replay_kind": "runtime_evidence",
                "action": "REDUCE_RISK",
            }
        }
        self.payloads = []

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

    heartbeat = node.crdt.payloads[-1]
    metrics = heartbeat["metrics"]

    assert metrics["simulation_replay_metrics_enabled"] is True
    assert metrics["simulation_replay_scenarios"] == 1
    assert metrics["simulation_replay_pending"] == 1
    assert metrics["simulation_replay_completed"] == 0
    assert metrics["simulation_replay_failed"] == 0
    assert metrics["simulation_replay_action_counts"]["REDUCE_RISK"] == 1