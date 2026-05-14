import pytest
from swarm_config import SwarmConfig

def test_sim_adapter(monkeypatch):
    monkeypatch.setenv("MARKET_MODE", "sim")
    monkeypatch.setenv("TOTAL_NODES", "4")
    SwarmConfig.model_config["env_file"] = None
    from mvp.lab_swarm_demo.node_agent import SwarmNode
    node = SwarmNode()
    assert node.market_mode == "sim"
    # В sim режиме market_adapter должен быть MultiPairAdapter
    assert "MultiPairAdapter" in type(node.market_adapter).__name__

def test_web3_adapter_creation(monkeypatch):
    monkeypatch.setenv("MARKET_MODE", "web3")
    monkeypatch.setenv("TOTAL_NODES", "4")
    SwarmConfig.model_config["env_file"] = None
    from mvp.lab_swarm_demo.node_agent import SwarmNode
    node = SwarmNode()
    assert node.market_mode == "web3"
    # Проверяем, что адаптер создался (без инициализации)
    assert node.market_adapter is not None