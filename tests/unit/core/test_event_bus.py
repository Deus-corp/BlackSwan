import asyncio
import pytest
from src.core.event_bus import EventBus

@pytest.mark.asyncio
async def test_publish_and_subscribe():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe("test_topic", handler)
    await bus.publish("test_topic", {"msg": "hello"}, "tester")
    assert len(received) == 1
    assert received[0]["payload"] == {"msg": "hello"}
    assert received[0]["topic"] == "test_topic"

@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe("test_topic", handler)
    await bus.publish("test_topic", {"msg": "first"})
    bus.unsubscribe("test_topic", handler)
    await bus.publish("test_topic", {"msg": "second"})
    assert len(received) == 1
    assert received[0]["payload"]["msg"] == "first"

@pytest.mark.asyncio
async def test_event_log():
    bus = EventBus()
    await bus.publish("economic", {"balance": 100}, "treasury")
    await bus.publish("security", {"alert": "debugger"}, "sentinella", sensitivity=4)
    log = bus.get_log()
    assert len(log) == 2
    economic_events = bus.get_log("economic")
    assert len(economic_events) == 1
    assert economic_events[0]["payload"] == {"balance": 100}