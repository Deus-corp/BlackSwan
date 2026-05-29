"""Trade policy and position sizing for the trade swarm node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.swarms.trade.context import RuntimeContext
from src.swarms.trade.market.snapshot import MarketSnapshot


@dataclass(slots=True, frozen=True)
class TradeIntent:
    """A normalized decision produced by the trade policy layer."""
    symbol: str
    side: str
    price: float
    confidence: float
    should_trade: bool
    reason: str = ""


class TradePolicy:
    """Determines whether trading is allowed for the current market state."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIntent:
        """Evaluate market state and return a trade intent."""
        symbol = snapshot.best_symbol
        market = snapshot.best_market
        price = snapshot.price_for(symbol)

        if price <= 0.0:
            return TradeIntent(
                symbol=symbol,
                side=self._default_side(),
                price=0.0,
                confidence=0.0,
                should_trade=False,
                reason="non_positive_price",
            )

        # Check survival constraints
        expected_return = price * float(getattr(self._ctx.config, "expected_return_rate", 0.0))
        _, survival_approved = self._ctx.survival.evaluate_trade(self._ctx.capital, expected_return)
        
        if not survival_approved:
            return TradeIntent(
                symbol=symbol,
                side=self._default_side(),
                price=price,
                confidence=0.0,
                should_trade=False,
                reason="survival_rejected",
            )

        # Update state
        if hasattr(self._ctx.risk_manager, "update_portfolio_value"):
            try:
                self._ctx.risk_manager.update_portfolio_value(self._ctx.capital)
            except Exception:
                pass

        # Risk management pre-trade checks
        order_value = self._estimated_order_value(snapshot)
        if hasattr(self._ctx.risk_manager, "pre_trade_check"):
            try:
                if not self._ctx.risk_manager.pre_trade_check(symbol, order_value):
                    return TradeIntent(symbol, self._default_side(), price, 0.0, False, "risk_manager_blocked")
            except Exception:
                return TradeIntent(symbol, self._default_side(), price, 0.0, False, "risk_manager_error")

        return TradeIntent(
            symbol=symbol,
            side=self._decide_side(market),
            price=price,
            confidence=self._confidence_from_market(market),
            should_trade=True,
            reason="approved",
        )

    def _default_side(self) -> str:
        side = str(getattr(self._ctx.config, "test_web3_swap_side", "buy")).lower().strip()
        return side if side in {"buy", "sell"} else "buy"

    def _estimated_order_value(self, snapshot: MarketSnapshot) -> float:
        price = snapshot.price_for(snapshot.best_symbol)
        amount = float(getattr(self._ctx.config, "test_web3_swap_amount", 0.0))
        return max(0.0, price * amount)

    def _decide_side(self, market: Dict[str, Any]) -> str:
        return self._default_side()

    @staticmethod
    def _confidence_from_market(market: Dict[str, Any]) -> float:
        spread = float(market.get("spread", 0.0))
        return max(0.0, min(1.0, 1.0 - spread))


class PositionSizer:
    """Converts a validated trade intent into a size constrained by risk rules."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    def size(self, intent: TradeIntent, market: MarketSnapshot) -> float:
        """Calculate position size based on current capital and risk budget."""
        if not intent.should_trade:
            return 0.0

        capital = max(0.0, float(getattr(self._ctx, "capital", 0.0)))
        base_amount = float(getattr(self._ctx.config, "test_web3_swap_amount", 0.0))
        
        stop_loss_ratio = self._stop_loss_ratio()
        stop_loss_distance = max(1e-9, intent.price * stop_loss_ratio)
        
        risk_based_size = self._risk_budget(capital) / stop_loss_distance
        capital_based_size = capital / max(1e-9, intent.price)
        
        # Apply constraints
        sized = min(base_amount, risk_based_size, capital_based_size)
        return max(0.0, sized * max(0.25, min(1.0, intent.confidence)))

    def _risk_budget(self, capital: float) -> float:
        params = getattr(self._ctx, "current_params", {})
        max_risk = float(params.get("max_risk_per_trade", 0.05)) if isinstance(params, dict) else 0.05
        return capital * max(0.005, min(0.15, max_risk))

    def _stop_loss_ratio(self) -> float:
        params = getattr(self._ctx, "current_params", {})
        if isinstance(params, dict):
            return max(0.001, min(0.2, float(params.get("stop_loss_ratio", 0.05))))
        return 0.05