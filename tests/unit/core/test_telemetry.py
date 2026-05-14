import pytest
from mvp.lab_swarm_demo.telemetry import Telemetry

class FakeEventStore:
    def __init__(self):
        self.events = []
    def append(self, event):
        self.events.append(event)

class FakeTelegram:
    async def send(self, msg):
        pass

def test_telemetry_heartbeat():
    store = FakeEventStore()
    tel = Telemetry("node-1", store, FakeTelegram(), lambda: (0,0), lambda x: None)
    tel.heartbeat(100, 1000.0, 0.05, 0.9, 0.8, 5, 3, {"exploration":2}, "trace-1")
    # Проверяем, что событие попало в стор
    assert len(store.events) == 1
    # Дополнительно можно проверить, что событие создано (не None)
    assert store.events[0] is not None