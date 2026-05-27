import pytest

from src.swarms.memory.node import MemorySwarmNode
from src.swarms.memory.shared_bridge import SharedMemoryBridge
from src.swarms.simulation.node import SimulationSwarmNode


class DummyCRDT:
    def __init__(self) -> None:
        self.state = {}
        self.payloads = []

    async def add_genome(self, payload):
        self.payloads.append(payload)
        record_id = str(payload.get("id") or len(self.state))
        self.state[record_id] = payload


@pytest.mark.asyncio
async def test_simulation_node_publishes_shared_memory_event() -> None:
    crdt = DummyCRDT()

    simulation = SimulationSwarmNode(node_id="simulation-test", heartbeat_interval_seconds=1.0)
    simulation.crdt = crdt

    record_id = await simulation.publish_memory_event(
        "scenario completed",
        topic="scenario_result",
        payload={"score": 0.82},
    )

    assert record_id
    assert simulation.memory_records_published == 1
    assert crdt.payloads

    payload = crdt.payloads[-1]

    assert payload["type"] == "memory_record"
    assert payload["kind"] == "event"
    assert payload["scope"] == "shared"
    assert payload["topic"] == "scenario_result"
    assert payload["source"]["originNodeId"] == "simulation-test"
    assert payload["source"]["swarm"] == "simulation"
    assert payload["payload"]["score"] == 0.82


@pytest.mark.asyncio
async def test_memory_swarm_ingests_simulation_published_memory_event() -> None:
    crdt = DummyCRDT()

    simulation = SimulationSwarmNode(node_id="simulation-test", heartbeat_interval_seconds=1.0)
    simulation.crdt = crdt

    memory = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    memory.crdt = crdt

    await simulation.publish_memory_event(
        "scenario completed",
        topic="scenario_result",
        payload={"score": 0.82},
    )

    bridge = SharedMemoryBridge()
    result = await bridge.ingest_from_crdt(crdt, memory)

    assert result["accepted"] == 1

    records = await memory.memory.recall(
        {
            "kind": "event",
            "scope": "shared",
            "swarm": "simulation",
            "text": "scenario completed",
        }
    )

    assert len(records) == 1
    assert records[0].source["swarm"] == "simulation"
    assert records[0].payload["score"] == 0.82