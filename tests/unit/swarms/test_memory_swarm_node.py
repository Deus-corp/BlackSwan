import pytest

from src.swarms.memory.node import MemorySwarmNode


class DummyCRDT:
    def __init__(self) -> None:
        self.payloads = []

    async def add_genome(self, payload):
        self.payloads.append(payload)


@pytest.mark.asyncio
async def test_memory_swarm_node_publishes_real_memory_metrics() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    await node.remember_event("hello memory", topic="test")
    await node.publish_heartbeat()

    assert node.crdt.payloads

    payload = node.crdt.payloads[-1]

    assert payload["type"] == "swarm_heartbeat"
    assert payload["swarm"] == "memory"
    assert payload["node_id"] == "memory-test"

    metrics = payload["metrics"]

    assert metrics["total_records"] == 1
    assert metrics["records_ingested"] == 1
    assert metrics["by_kind"]["event"] == 1
    assert metrics["by_scope"]["own"] == 1
    assert metrics["verified_records"] == 1
    assert metrics["episodic_records"] == 1

@pytest.mark.asyncio
async def test_memory_swarm_node_ingests_external_record_through_quarantine() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "event",
            "scope": "shared",
            "topic": "external",
            "payload": {"message": "external memory", "tags": ["external"]},
            "source": {
                "originNodeId": "trusted-node",
                "swarm": "trade",
                "parents": [],
            },
            "confidence": 0.9,
        }
    )

    assert accepted is True
    assert node.records_ingested == 1
    assert node.records_rejected == 0

    stats = await node.memory.stats()
    assert stats.total_records == 1
    assert stats.by_scope["shared"] == 1
    assert stats.by_kind["event"] == 1


@pytest.mark.asyncio
async def test_memory_swarm_node_rejects_low_confidence_record() -> None:
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = DummyCRDT()

    accepted = await node.ingest_record(
        {
            "kind": "event",
            "scope": "shared",
            "topic": "external",
            "payload": {"message": "low confidence"},
            "source": {
                "originNodeId": "trusted-node",
                "swarm": "trade",
                "parents": [],
            },
            "confidence": 0.1,
        }
    )

    assert accepted is False
    assert node.records_ingested == 0
    assert node.records_rejected == 1

    stats = await node.memory.stats()
    assert stats.total_records == 0