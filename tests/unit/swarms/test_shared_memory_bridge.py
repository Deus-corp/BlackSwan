import pytest
import time

from src.swarms.memory.node import MemorySwarmNode
from src.swarms.memory.shared_bridge import SharedMemoryBridge
from src.memory.publisher import publish_memory_record
from src.core.crdt_adapter import CRDTAdapter


class DummyCRDT:
    def __init__(self) -> None:
        self.state = {}

    async def add_genome(self, payload):
        record_id = str(payload.get("id") or len(self.state))
        self.state[record_id] = payload


@pytest.mark.asyncio
async def test_shared_memory_bridge_ingests_memory_record() -> None:
    crdt = DummyCRDT()
    crdt.state["rec-1"] = {
        "type": "memory_record",
        "kind": "fact",
        "scope": "shared",
        "topic": "architecture",
        "payload": {
            "subject": "BlackSwan",
            "predicate": "has",
            "object": "memory swarm",
            "tags": ["architecture"],
        },
        "source": {
            "originNodeId": "trade-1",
            "swarm": "trade",
            "parents": [],
        },
        "confidence": 0.95,
    }

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    bridge = SharedMemoryBridge()
    result = await bridge.ingest_from_crdt(crdt, node)

    assert result["scanned"] == 1
    assert result["accepted"] == 1
    assert result["rejected"] == 0

    stats = await node.memory.stats()
    assert stats.total_records == 1
    assert stats.by_kind["fact"] == 1
    assert stats.by_scope["shared"] == 1


@pytest.mark.asyncio
async def test_shared_memory_bridge_ingests_swarm_event() -> None:
    crdt = DummyCRDT()
    crdt.state["event-1"] = {
        "type": "swarm_event",
        "swarm": "simulation",
        "node_id": "simulation-1",
        "event": "scenario_completed",
        "payload": {
            "scenario": "basic",
            "score": 0.7,
        },
        "severity": "info",
    }

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    bridge = SharedMemoryBridge(include_swarm_events=True)
    result = await bridge.ingest_from_crdt(crdt, node)

    assert result["accepted"] == 1

    records = await node.memory.recall({"kind": "event", "scope": "shared", "text": "scenario_completed"})
    assert len(records) == 1
    assert records[0].source["swarm"] == "simulation"


@pytest.mark.asyncio
async def test_shared_memory_bridge_skips_seen_records() -> None:
    crdt = DummyCRDT()
    crdt.state["rec-1"] = {
        "type": "memory_record",
        "kind": "event",
        "scope": "shared",
        "payload": {"message": "hello"},
        "source": {"originNodeId": "trade-1", "parents": []},
        "confidence": 0.9,
    }

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    bridge = SharedMemoryBridge()

    first = await bridge.ingest_from_crdt(crdt, node)
    second = await bridge.ingest_from_crdt(crdt, node)

    assert first["accepted"] == 1
    assert second["scanned"] == 0
    assert second["accepted"] == 0

    stats = await node.memory.stats()
    assert stats.total_records == 1

@pytest.mark.asyncio
async def test_shared_memory_bridge_ingests_published_memory_record() -> None:
    crdt = DummyCRDT()
    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    await publish_memory_record(
        crdt,
        kind="experience",
        scope="shared",
        topic="simulation_result",
        payload={"score": 0.8, "tags": ["simulation"]},
        source_node_id="simulation-1",
        swarm="simulation",
        confidence=0.95,
        record_id="mem-published-1",
    )

    bridge = SharedMemoryBridge()
    result = await bridge.ingest_from_crdt(crdt, node)

    assert result["accepted"] == 1

    records = await node.memory.recall(
        {
            "kind": "experience",
            "scope": "shared",
            "swarm": "simulation",
            "text": "simulation_result",
        }
    )

    assert len(records) == 1
    assert records[0].id == "mem-published-1"

@pytest.mark.asyncio
async def test_shared_memory_bridge_skips_non_memory_payloads_without_marking_seen() -> None:
    crdt = DummyCRDT()
    crdt.state["hb-1"] = {
        "type": "swarm_heartbeat",
        "swarm": "simulation",
        "node_id": "simulation-1",
    }

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    bridge = SharedMemoryBridge()
    result = await bridge.ingest_from_crdt(crdt, node)

    assert result["scanned"] == 0
    assert result["accepted"] == 0
    assert result["rejected"] == 0
    assert result["skipped"] == 1
    assert result["seen"] == 0
    assert bridge.stats()["skipped_records"] == 1

@pytest.mark.asyncio
async def test_memory_scan_shared_memory_refreshes_crdt_storage(tmp_path) -> None:
    db_path = tmp_path / "shared_crdt.sqlite3"

    writer = CRDTAdapter(node_id="simulation-test", db_path=str(db_path))
    memory = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    memory.crdt = CRDTAdapter(node_id="memory-test", db_path=str(db_path))
    memory.ingest_records_since_start = False

    await writer.add_genome(
        {
            "type": "memory_record",
            "id": "mem-refresh-1",
            "kind": "event",
            "scope": "shared",
            "topic": "refresh_test",
            "payload": {"message": "hello from another process"},
            "source": {
                "originNodeId": "simulation-test",
                "swarm": "simulation",
                "parents": [],
            },
            "confidence": 0.95,
        }
    )

    result = await memory.scan_shared_memory()

    assert result["accepted"] == 1

    records = await memory.memory.recall(
        {
            "kind": "event",
            "scope": "shared",
            "swarm": "simulation",
            "text": "another process",
        }
    )

    assert len(records) == 1
    assert records[0].id == "mem-refresh-1"

@pytest.mark.asyncio
async def test_shared_memory_bridge_filters_records_before_min_timestamp() -> None:
    crdt = DummyCRDT()
    now = time.time()

    crdt.state["old-rec"] = {
        "type": "memory_record",
        "kind": "event",
        "scope": "shared",
        "payload": {"message": "old"},
        "source": {"originNodeId": "simulation-1", "swarm": "simulation", "parents": []},
        "confidence": 0.95,
        "timestamp": now - 100,
    }
    crdt.state["new-rec"] = {
        "type": "memory_record",
        "kind": "event",
        "scope": "shared",
        "payload": {"message": "new"},
        "source": {"originNodeId": "simulation-1", "swarm": "simulation", "parents": []},
        "confidence": 0.95,
        "timestamp": now + 1,
    }

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    bridge = SharedMemoryBridge()
    result = await bridge.ingest_from_crdt(crdt, node, min_timestamp=now)

    assert result["accepted"] == 1
    assert result["skipped"] == 1

    records = await node.memory.recall({"kind": "event", "scope": "shared", "text": "new"})
    assert len(records) == 1

@pytest.mark.asyncio
async def test_shared_memory_bridge_skips_swarm_events_by_default() -> None:
    crdt = DummyCRDT()
    crdt.state["event-1"] = {
        "type": "swarm_event",
        "swarm": "simulation",
        "node_id": "simulation-1",
        "event": "scenario_completed",
        "payload": {"scenario": "basic"},
        "severity": "info",
    }

    node = MemorySwarmNode(node_id="memory-test", heartbeat_interval_seconds=1.0)
    node.crdt = crdt

    bridge = SharedMemoryBridge()
    result = await bridge.ingest_from_crdt(crdt, node)

    assert result["accepted"] == 0
    assert result["skipped"] == 1

    stats = await node.memory.stats()
    assert stats.total_records == 0