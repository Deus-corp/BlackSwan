"""Trade policy and position sizing for the trade swarm node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .context import RuntimeContext
from .market.snapshot import MarketSnapshot


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

        expected_return_amount = price * float(getattr(self._ctx.config, "expected_return_rate", 0.0))
        _, survival_approved = self._ctx.survival.evaluate_trade(
            self._ctx.capital,
            expected_return_amount,
        )
        if not survival_approved:
            return TradeIntent(
                symbol=symbol,
                side=self._default_side(),
                price=price,
                confidence=0.0,
                should_trade=False,
                reason="survival_rejected",
            )

        if hasattr(self._ctx.risk_manager, "update_portfolio_value"):
            try:
                self._ctx.risk_manager.update_portfolio_value(self._ctx.capital)
            except Exception:
                pass

        order_value = self._estimated_order_value(snapshot)
        if hasattr(self._ctx.risk_manager, "pre_trade_check"):
            try:
                if not self._ctx.risk_manager.pre_trade_check(symbol, order_value):
                    return TradeIntent(
                        symbol=symbol,
                        side=self._default_side(),
                        price=price,
                        confidence=0.0,
                        should_trade=False,
                        reason="risk_manager_blocked",
                    )
            except Exception:
                return TradeIntent(
                    symbol=symbol,
                    side=self._default_side(),
                    price=price,
                    confidence=0.0,
                    should_trade=False,
                    reason="risk_manager_error",
                )

        side = self._decide_side(market)
        confidence = self._confidence_from_market(market)

        return TradeIntent(
            symbol=symbol,
            side=side,
            price=price,
            confidence=confidence,
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
        side = self._default_side()
        return side

    @staticmethod
    def _confidence_from_market(market: Dict[str, Any]) -> float:
        try:
            if market.get("spread") is not None:
                spread = float(market.get("spread", 0.0))
                return max(0.0, min(1.0, 1.0 - spread))
        except Exception:
            pass
        return 0.5


class PositionSizer:
    """Converts a validated trade intent into a size constrained by risk rules."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    def size(self, intent: TradeIntent, market: MarketSnapshot) -> float:
        if not intent.should_trade:
            return 0.0

        capital = max(0.0, float(getattr(self._ctx, "capital", 0.0)))
        base_amount = float(getattr(self._ctx.config, "test_web3_swap_amount", 0.0))
        risk_budget = self._risk_budget(capital)
        stop_loss_ratio = self._stop_loss_ratio()
        stop_loss_distance = max(1e-9, intent.price * stop_loss_ratio)

        risk_based_size = risk_budget / stop_loss_distance
        capital_based_size = capital / max(1e-9, intent.price)
        sized = min(base_amount, risk_based_size, capital_based_size)

        confidence = max(0.0, min(1.0, intent.confidence))
        sized *= max(0.25, confidence)

        return max(0.0, sized)

    def _risk_budget(self, capital: float) -> float:
        current_params = getattr(self._ctx, "current_params", {})
        if isinstance(current_params, dict):
            max_risk = float(current_params.get("max_risk_per_trade", 0.05))
        else:
            max_risk = 0.05
        max_risk = max(0.005, min(0.15, max_risk))
        return capital * max_risk

    def _stop_loss_ratio(self) -> float:
        current_params = getattr(self._ctx, "current_params", {})
        if isinstance(current_params, dict):
            try:
                return max(0.001, min(0.2, float(current_params.get("stop_loss_ratio", 0.05))))
            except Exception:
                pass
        return 0.05