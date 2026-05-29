from dataclasses import dataclass, replace

import pytest

from src.swarms.common.protocols.directives import (
    DirectiveStatus,
    build_directive,
)
from src.swarms.trade.node_core.directive_consumer import apply_trade_directive


@dataclass(frozen=True)
class DummyTradeConfig:
    dry_run: bool = False
    execution_enabled: bool = True


class DummyContext:
    def __init__(self, config: DummyTradeConfig) -> None:
        self.config = config


class DummyNode:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.trade_config = DummyTradeConfig()
        self.ctx = DummyContext(self.trade_config)
        self._processed_directive_ids = set()
        self.events = []

    async def _emit_trade_event(self, *, event_type, parent_gid=None, payload=None):
        self.events.append(
            {
                "event_type": event_type,
                "parent_gid": parent_gid,
                "payload": payload or {},
            }
        )


@pytest.mark.asyncio
async def test_apply_trade_reduce_risk_directive_forces_dry_run() -> None:
    node = DummyNode()
    directive = build_directive(
        directive_id="dir-1",
        action="REDUCE_RISK",
        source="overseer",
        target_type="swarm",
        target="trade",
    )

    result = await apply_trade_directive(node, directive.to_dict())

    assert result["status"] == DirectiveStatus.APPLIED.value
    assert node.trade_config.dry_run is True
    assert node.trade_config.execution_enabled is False
    assert node.ctx.config is node.trade_config
    assert node.events[0]["event_type"] == "directive_applied"
    assert node.events[0]["parent_gid"] == "dir-1"


@pytest.mark.asyncio
async def test_apply_trade_observe_directive_acknowledges_only() -> None:
    node = DummyNode()
    directive = build_directive(
        directive_id="dir-2",
        action="OBSERVE",
        source="overseer",
        target_type="swarm",
        target="trade",
    )

    result = await apply_trade_directive(node, directive.to_dict())

    assert result["status"] == DirectiveStatus.ACKNOWLEDGED.value
    assert node.trade_config.dry_run is False
    assert node.events == []


@pytest.mark.asyncio
async def test_apply_trade_directive_rejects_unsafe_action() -> None:
    node = DummyNode()
    directive = build_directive(
        directive_id="dir-3",
        action="ENABLE_EXECUTION",
        source="overseer",
        target_type="swarm",
        target="trade",
    )

    result = await apply_trade_directive(node, directive.to_dict())

    assert result["status"] == DirectiveStatus.REJECTED.value
    assert "Unsupported or unsafe" in result["message"]


@pytest.mark.asyncio
async def test_apply_trade_directive_rejects_wrong_target() -> None:
    node = DummyNode()
    directive = build_directive(
        directive_id="dir-4",
        action="REDUCE_RISK",
        source="overseer",
        target_type="swarm",
        target="memory",
    )

    result = await apply_trade_directive(node, directive.to_dict())

    assert result["status"] == DirectiveStatus.REJECTED.value
    assert "does not target" in result["message"]