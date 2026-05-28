from src.swarms.overseer.overseer_core.collector import StateCollector


def test_state_collector_selects_latest_memory_heartbeat_by_node_timestamp() -> None:
    collector = StateCollector.__new__(StateCollector)

    heartbeats = [
        {
            "type": "swarm_heartbeat",
            "swarm": "memory",
            "node_id": "memory-1",
            "timestamp": 1.0,
            "metrics": {
                "heartbeats_published": 0,
                "gold_candidates": 0,
            },
        },
        {
            "type": "swarm_heartbeat",
            "swarm": "memory",
            "node_id": "memory-1",
            "timestamp": 2.0,
            "metrics": {
                "heartbeats_published": 2,
                "gold_candidates": 2,
            },
        },
    ]

    latest = collector._latest_heartbeats_by_swarm(heartbeats)

    assert latest["memory"]["memory-1"]["metrics"]["gold_candidates"] == 2

def test_state_collector_refreshes_state_source() -> None:
    collector = StateCollector.__new__(StateCollector)

    class DummyStateSource:
        def __init__(self) -> None:
            self.refreshed = False
            self.state = {}

        def refresh_from_storage(self) -> None:
            self.refreshed = True

    source = DummyStateSource()
    collector._state_source = source

    collector._refresh_state_source()

    assert source.refreshed is True

def test_state_collector_collect_refreshes_before_reading_state() -> None:
    class DummyStateSource:
        def __init__(self) -> None:
            self.refreshed = False
            self.state = {}

        def refresh_from_storage(self) -> None:
            self.refreshed = True

    source = DummyStateSource()
    collector = StateCollector(source)

    collector.collect()

    assert source.refreshed is True