from src.swarms.trade.node_core.crdt_refresh import refresh_crdt_state


class DummyAdapter:
    def __init__(self) -> None:
        self.state = {}
        self.called = False

    def refresh_from_storage(self) -> int:
        self.called = True
        self.state = {
            "dir-1": {
                "type": "swarm_directive",
                "directive_id": "dir-1",
                "action": "REDUCE_RISK",
            }
        }
        return len(self.state)


class DummyNode:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.crdt = DummyAdapter()


def test_refresh_crdt_state_uses_adapter_refresh_from_storage() -> None:
    node = DummyNode()

    count = refresh_crdt_state(node)

    assert count == 1
    assert node.crdt.called is True
    assert node.crdt.state["dir-1"]["type"] == "swarm_directive"