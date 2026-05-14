import pytest
from swarm_config import SwarmConfig

def test_config_defaults():
    config = SwarmConfig()
    assert config.node_id is not None
    assert config.total_nodes == 4
    assert config.expected_return_rate > 0
    assert config.market_mode in ("sim", "web3", "live", "futures")

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("TOTAL_NODES", "10")
    monkeypatch.setenv("MARKET_MODE", "sim")
    config = SwarmConfig()
    assert config.total_nodes == 10
    assert config.market_mode == "sim"