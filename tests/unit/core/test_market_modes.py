import pytest
from swarm_config import SwarmConfig
import swarm_config


def test_sim_adapter(monkeypatch):
    monkeypatch.setenv("MARKET_MODE", "sim")
    monkeypatch.setenv("TOTAL_NODES", "4")
    swarm_config.config = SwarmConfig()
    from mvp.lab_swarm_demo.trade_node_agent import SwarmNode
    node = SwarmNode()
    assert node.market_adapter is not None


def test_web3_adapter_creation(monkeypatch):
    monkeypatch.setenv("MARKET_MODE", "web3")
    monkeypatch.setenv("TOTAL_NODES", "4")
    swarm_config.config = SwarmConfig()
    from mvp.lab_swarm_demo.trade_node_agent import SwarmNode
    node = SwarmNode()
    assert node.market_adapter is not None