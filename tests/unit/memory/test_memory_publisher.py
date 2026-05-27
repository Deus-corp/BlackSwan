import pytest

from src.memory.publisher import build_memory_record_event, publish_memory_record


class DummyCRDT:
    def __init__(self) -> None:
        self.payloads = []

    async def add_genome(self, payload):
        self.payloads.append(payload)


def test_build_memory_record_event_normalizes_payload_and_tags() -> None:
    event = build_memory_record_event(
        kind="experience",
        scope="shared",
        topic="trade_outcome",
        payload={"score": 0.9, "tags": ["trade"]},
        source_node_id="trade-1",
        swarm="trade",
        tags=["experience", "trade"],
        confidence=1.5,
        priority=999,
        record_id="mem-1",
    )

    assert event["type"] == "memory_record"
    assert event["id"] == "mem-1"
    assert event["kind"] == "experience"
    assert event["scope"] == "shared"
    assert event["topic"] == "trade_outcome"
    assert event["payload"]["score"] == 0.9
    assert event["payload"]["tags"] == ["experience", "trade"]
    assert event["source"]["originNodeId"] == "trade-1"
    assert event["source"]["swarm"] == "trade"
    assert event["confidence"] == 1.0
    assert event["priority"] == 100


def test_build_memory_record_event_rejects_missing_identity() -> None:
    with pytest.raises(ValueError):
        build_memory_record_event(
            kind="event",
            payload={"message": "missing source"},
            source_node_id="",
            swarm="trade",
        )

    with pytest.raises(ValueError):
        build_memory_record_event(
            kind="event",
            payload={"message": "missing swarm"},
            source_node_id="node-a",
            swarm="",
        )


@pytest.mark.asyncio
async def test_publish_memory_record_adds_payload_to_crdt() -> None:
    crdt = DummyCRDT()

    record_id = await publish_memory_record(
        crdt,
        kind="event",
        scope="shared",
        topic="test",
        payload="hello",
        source_node_id="simulation-1",
        swarm="simulation",
        confidence=0.9,
        record_id="mem-2",
    )

    assert record_id == "mem-2"
    assert len(crdt.payloads) == 1

    payload = crdt.payloads[0]

    assert payload["type"] == "memory_record"
    assert payload["payload"]["value"] == "hello"
    assert payload["source"]["originNodeId"] == "simulation-1"
    assert payload["source"]["swarm"] == "simulation"