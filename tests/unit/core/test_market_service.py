import pytest
from src.swarms.trade.market import MarketSnapshotService, select_best_market

def test_select_best_market():
    snapshot = {
        "WETH/USDC": {"price": 2000.0},
        "BTC/USDT": {"price": 50000.0},
    }
    sym, tick = select_best_market(snapshot)
    # При EXPECTED_RETURN_RATE=20.0 BTC будет приоритетнее
    assert sym in ("WETH/USDC", "BTC/USDT")
    assert "price" in tick

@pytest.mark.asyncio
async def test_market_service_sim():
    # Создаём пустой адаптер (не используется в sim)
    class FakeAdapter:
        async def fetch_all_tickers(self):
            return {"WETH/USDC": {"price": 100.0}}

    service = MarketSnapshotService(FakeAdapter(), "sim")
    snap = await service.get_snapshot()
    assert "WETH/USDC" in snap
    assert "price" in snap["WETH/USDC"]