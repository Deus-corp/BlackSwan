"""Trading orchestration flow for trade swarm nodes.

Coordinates policy evaluation, sizing, execution, telemetry, and hedge handling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Final

from ..context import RuntimeContext
from ..market.snapshot import MarketSnapshot
from ..risk import TradePolicy, PositionSizer, TradeIntent

logger: Final = logging.getLogger("SwarmNode.TradeFlow")


class TradeFlowService:
    """
    Coordinates trading decisions and execution lifecycle.

    Responsibilities:
    1. Evaluate market conditions via policy.
    2. Calculate position sizing.
    3. Execute orders through the executor.
    4. Update capital state and publish telemetry.
    5. Handle hedging logic.
    """

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx
        self._policy = TradePolicy(ctx)
        self._sizer = PositionSizer(ctx)

    async def process(self, snapshot: MarketSnapshot) -> Optional[Dict[str, Any]]:
        """
        Main orchestration entrypoint for trading logic.

        Args:
            snapshot: Current market state data.

        Returns:
            Dict containing trade execution results or None if no trade occurs.
        """
        intent = self._policy.evaluate(snapshot)

        if not intent.should_trade:
            logger.debug("Trade rejected: %s", intent.reason)
            return None

        amount = self._sizer.size(intent, snapshot)
        if amount <= 0:
            logger.debug("Trade skipped: size <= 0")
            return None

        return await self._execute(intent=intent, amount=amount)

    async def _execute(self, intent: TradeIntent, amount: float) -> Optional[Dict[str, Any]]:
        """
        Executes the trade and manages post-trade lifecycle.
        """
        symbol = intent.symbol
        side = intent.side
        prev_capital = self._ctx.capital

        try:
            trade_result = await self._ctx.executor.execute_order(
                symbol=symbol,
                side=side,
                amount=amount,
                price=intent.price,
                capital=self._ctx.capital,
            )
        except Exception as e:
            logger.exception("Critical failure during trade execution")
            trade_result = {"success": False, "status": str(e), "tx_hash": ""}

        self._apply_post_trade_capital(amount=amount, price=intent.price)

        if trade_result and trade_result.get("success"):
            await self._publish_trade(trade_result, symbol, side, amount, prev_capital)
            await self._handle_hedge(symbol=symbol, side=side, amount=amount)

        return trade_result

    def _apply_post_trade_capital(self, amount: float, price: float) -> None:
        """
        Applies synthetic capital state updates.
        """
        simulated_return = price * amount * 0.1
        self._ctx.capital *= (1 + simulated_return)
        
        manager = self._ctx.capital_manager
        manager.capital = self._ctx.capital
        manager.apply_dq_delta(0.001)

    async def _publish_trade(
        self, 
        trade_result: Dict[str, Any], 
        symbol: str, 
        side: str, 
        amount: float, 
        prev_capital: float
    ) -> None:
        """
        Publishes execution telemetry to the monitoring system.
        """
        try:
            self._ctx.telemetry.update_impact(self._ctx.capital)
            await self._ctx.telemetry.trade(
                step=self._ctx.step_count,
                symbol=symbol,
                side=side,
                amount=amount,
                tx_hash=trade_result.get("tx_hash", ""),
                status=trade_result.get("status", "unknown"),
                capital_before=prev_capital,
                capital_after=self._ctx.capital,
                trace_id=self._ctx.trace_id,
            )
        except Exception:
            logger.exception("Telemetry publishing failed")

    async def _handle_hedge(self, symbol: str, side: str, amount: float) -> None:
        """
        Executes secondary hedge orders if conditions are met.
        """
        if self._ctx.config.market_mode != "futures":
            return

        if not getattr(self._ctx.market_adapter, "hedge_enabled", False):
            return

        hedge_amount = abs(amount) * self._ctx.config.hedge_ratio
        if hedge_amount <= 0:
            return

        hedge_side = "sell" if side == "buy" else "buy"
        try:
            spot_adapter = self._ctx.market_adapter.get_adapter(symbol, "spot")
            if spot_adapter:
                await spot_adapter.place_order(symbol, hedge_side, hedge_amount)
                logger.info("Hedge order placed for %s", symbol)
        except Exception:
            logger.exception("Hedge execution failed")