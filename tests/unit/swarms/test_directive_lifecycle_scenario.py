from dataclasses import dataclass

import pytest

from src.swarms.common.protocols.briefs import build_brief_item, build_swarm_brief
from src.swarms.common.protocols.directives import DirectiveStatus
from src.swarms.overseer.overseer_core.directive_emitter import build_directives_from_brief
from src.swarms.trade.node_core.directive_consumer import apply_trade_directive


@dataclass(frozen=True)
class DummyTradeConfig:
    dry_run: bool = False
    execution_enabled: bool = True


class DummyTradeContext:
    def __init__(self, config: DummyTradeConfig) -> None:
        self.config = config


class DummyTradeNode:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.trade_config = DummyTradeConfig()
        self.ctx = DummyTradeContext(self.trade_config)
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
async def test_overseer_brief_to_trade_reduce_risk_lifecycle() -> None:
    brief = build_swarm_brief(
        brief_id="brief-risk-1",
        scope="global",
        status="degraded",
        summary="Trade risk should be reduced.",
        recommended_actions=[
            build_brief_item(
                title="reduce trade risk",
                severity="warning",
                payload={"directive": "REDUCE_RISK"},
            )
        ],
    )

    directives = build_directives_from_brief(brief, source="overseer-1")

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "REDUCE_RISK"
    assert directive.target == "trade"

    node = DummyTradeNode()
    result = await apply_trade_directive(node, directive.to_dict())

    assert result["type"] == "swarm_directive_result"
    assert result["directive_id"] == directive.directive_id
    assert result["status"] == DirectiveStatus.APPLIED.value
    assert result["swarm"] == "trade"

    assert node.trade_config.dry_run is True
    assert node.trade_config.execution_enabled is False
    assert node.ctx.config is node.trade_config

    assert node.events == [
        {
            "event_type": "directive_applied",
            "parent_gid": directive.directive_id,
            "payload": {
                "action": "REDUCE_RISK",
                "dry_run": True,
                "execution_enabled": False,
            },
        }
    ]

from src.memory.directive_consumer import apply_memory_directive


class DummyMemoryNode:
    def __init__(self) -> None:
        self.node_id = "memory-1"
        self._processed_directive_ids = set()
        self.last_memory_summary = {
            "gold_candidates": 3,
            "review_candidates": 0,
            "alert_candidates": 0,
            "dedupe_candidates": 0,
        }


@pytest.mark.asyncio
async def test_overseer_brief_to_memory_promote_gold_lifecycle() -> None:
    brief = build_swarm_brief(
        brief_id="brief-gold-1",
        scope="global",
        status="healthy",
        summary="Memory has gold candidates.",
        recommended_actions=[
            build_brief_item(
                title="promote memory gold candidates",
                severity="info",
                payload={"directive": "PROMOTE_GOLD_CANDIDATES"},
            )
        ],
    )

    directives = build_directives_from_brief(brief, source="overseer-1")

    assert len(directives) == 1
    directive = directives[0]
    assert directive.action == "PROMOTE_GOLD_CANDIDATES"
    assert directive.target == "memory"

    node = DummyMemoryNode()
    result = await apply_memory_directive(node, directive.to_dict())

    assert result["type"] == "swarm_directive_result"
    assert result["directive_id"] == directive.directive_id
    assert result["status"] == DirectiveStatus.APPLIED.value
    assert result["swarm"] == "memory"
    assert result["payload"]["gold_candidates"] == 3
    assert result["payload"]["next_step"] == "export_or_replay_gold_candidates"