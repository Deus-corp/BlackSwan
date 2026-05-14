import pytest
from swarm_config import SwarmConfig

@pytest.mark.asyncio
async def test_node_creation_sim(monkeypatch):
    """Узел должен создаваться в sim-режиме без ошибок."""
    monkeypatch.setenv("MARKET_MODE", "sim")
    monkeypatch.setenv("TOTAL_NODES", "4")
    monkeypatch.setenv("PEERS", "")
    
    # Перечитываем конфиг (pydantic-settings кеширует, поэтому форсим)
    from swarm_config import SwarmConfig
    SwarmConfig.model_config["env_file"] = None  # отключаем .env для теста
    
    from mvp.lab_swarm_demo.node_agent import SwarmNode
    node = SwarmNode()
    assert node.node_id is not None
    assert node.market_mode == "sim"
    assert node.engine is not None
    assert node.capital == 1000.0

@pytest.mark.asyncio
async def test_node_creation_web3(monkeypatch):
    """Узел должен создаваться в web3-режиме (без реального провайдера — просто структура)."""
    monkeypatch.setenv("MARKET_MODE", "web3")
    monkeypatch.setenv("TOTAL_NODES", "4")
    from swarm_config import SwarmConfig
    SwarmConfig.model_config["env_file"] = None
    from mvp.lab_swarm_demo.node_agent import SwarmNode
    node = SwarmNode()
    assert node.market_mode == "web3"
    # Не требуем реального RPC, просто проверяем, что адаптер создался
    assert node.market_adapter is not None