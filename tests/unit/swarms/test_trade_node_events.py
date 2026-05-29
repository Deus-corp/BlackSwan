import pytest

from src.core.events import Event
from src.swarms.trade.node_core.events import emit_trade_event


class DummyEventBus:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


class DummyEventStore:
    def __init__(self) -> None:
        self.events = []

    def append(self, event: Event) -> None:
        self.events.append(event)


class DummyCRDT:
    def __init__(self) -> None:
        self.items = []

    async def add_genome(self, item):
        self.items.append(item)


@pytest.mark.asyncio
async def test_emit_trade_event_publishes_to_all_sinks() -> None:
    event_bus = DummyEventBus()
    event_store = DummyEventStore()
    crdt = DummyCRDT()

    event = await emit_trade_event(
        event_bus=event_bus,
        event_store=event_store,
        crdt=crdt,
        node_id="trade-1",
        event_type="command_applied",
        payload={"action": "PAUSE"},
        parent_id="parent-1",
    )

    assert event.type == "command_applied"
    assert event.node_id == "trade-1"
    assert event.parent_id == "parent-1"
    assert event.payload["action"] == "PAUSE"
    assert event.payload["trace_id"] == "parent-1"

    assert event_bus.events == [event]
    assert event_store.events == [event]

    assert len(crdt.items) == 1
    assert crdt.items[0]["type"] == "swarm_event"
    assert crdt.items[0]["event_type"] == "command_applied"
    assert crdt.items[0]["source_node"] == "trade-1"
    assert crdt.items[0]["payload"]["action"] == "PAUSE"
    assert crdt.items[0]["payload"]["trace_id"] == "parent-1"


@pytest.mark.asyncio
async def test_emit_trade_event_works_without_optional_sinks() -> None:
    event = await emit_trade_event(
        event_bus=None,
        event_store=None,
        crdt=None,
        node_id="trade-1",
        event_type="heartbeat",
        payload={},
    )

    assert event.type == "heartbeat"
    assert event.node_id == "trade-1"
    assert event.payload["trace_id"]