from src.swarms.trade.node_core.leadership import is_leader


class DummyNode:
    def __init__(self) -> None:
        self.seen_blocks = []

    def _is_leader_impl(self, block_number: int) -> bool:
        self.seen_blocks.append(block_number)
        return block_number % 2 == 0


def test_is_leader_delegates_to_impl() -> None:
    node = DummyNode()

    assert is_leader(node, 10) is True
    assert is_leader(node, 11) is False
    assert node.seen_blocks == [10, 11]