import pytest
from src.swarms.trade.domain.models import ExecutionResult, MarketSnapshot, TradeDecision

def test_market_snapshot():
    snap = MarketSnapshot(symbol="WETH/USDC", price=2000.0)
    assert snap.symbol == "WETH/USDC"
    assert snap.price == 2000.0

def test_trade_decision():
    d = TradeDecision(action="sell", amount=0.001, symbol="WETH/USDC", price=2000.0)
    assert d.action == "sell"

def test_execution_result():
    r = ExecutionResult(success=True, tx_hash="0xabc", status="success")
    assert r.success is True
    assert r.tx_hash == "0xabc"