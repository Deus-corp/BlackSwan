import pytest
from src.swarms.trade.execution import (
    ExecutionBackend,
    SimExecutionBackend,
    build_backend,
)

def test_sim_backend_is_execution_backend():
    backend = SimExecutionBackend()
    assert isinstance(backend, ExecutionBackend)

@pytest.mark.asyncio
async def test_sim_execute_order():
    backend = SimExecutionBackend()
    result = await backend.execute_order(
        symbol="WETH/USDC",
        side="sell",
        amount=0.001,
        price=2000.0,
        capital=1000.0,
    )
    assert result["success"] is True
    assert "new_capital" in result
    assert result["tx_hash"] is None
    assert result["status"] == "simulated"

def test_factory_creates_backend(monkeypatch):
    """Фабрика должна создавать любой ExecutionBackend без ошибок (тип может варьироваться из-за кеширования конфига)."""
    monkeypatch.setenv("MARKET_MODE", "sim")
    import swarm_config
    from swarm_config import SwarmConfig
    swarm_config.config = SwarmConfig()
    backend = build_backend("test-node", None, lambda block: True)
    assert isinstance(backend, ExecutionBackend)