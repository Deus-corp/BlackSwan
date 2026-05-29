from src.swarms.trade.node_core.configuration import (
    build_runtime_context,
    build_trade_config,
    pull_context,
    sync_context,
)


class DummyNode:
    def __init__(self) -> None:
        self.synced = False
        self.pulled = False
        self.trade_config = object()
        self.ctx = object()

    def _build_trade_config_impl(self):
        return self.trade_config

    def _build_runtime_context_impl(self):
        return self.ctx

    def _sync_context_impl(self) -> None:
        self.synced = True

    def _pull_context_impl(self) -> None:
        self.pulled = True


def test_configuration_helpers_delegate_to_impl_methods() -> None:
    node = DummyNode()

    assert build_trade_config(node) is node.trade_config
    assert build_runtime_context(node) is node.ctx

    sync_context(node)
    pull_context(node)

    assert node.synced is True
    assert node.pulled is True