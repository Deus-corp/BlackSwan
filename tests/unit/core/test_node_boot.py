import pytest
from swarm_config import SwarmConfig
import swarm_config

@pytest.mark.asyncio
async def test_node_creation_sim(monkeypatch):
    """Узел должен создаваться в sim-режиме без ошибок."""
    monkeypatch.setenv("MARKET_MODE", "sim")
    monkeypatch.setenv("TOTAL_NODES", "4")
    monkeypatch.setenv("PEERS", "")
    swarm_config.config = SwarmConfig()
    from src.swarms.trade.node import SwarmNode
    node = SwarmNode()
    assert node.node_id is not None
    assert node.engine is not None
    assert node.capital == 1000.0

@pytest.mark.asyncio
async def test_node_creation_web3(monkeypatch):
    """Узел должен создаваться в web3-режиме (без реального провайдера)."""
    monkeypatch.setenv("MARKET_MODE", "web3")
    monkeypatch.setenv("TOTAL_NODES", "4")
    swarm_config.config = SwarmConfig()
    from src.swarms.trade.node import SwarmNode
    node = SwarmNode()
    assert node.node_id is not None
    assert node.market_adapter is not None