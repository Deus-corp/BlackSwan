"""Trading orchestration flow for trade swarm nodes.

This service replaces the old inline trade execution logic from node.py.
It coordinates policy evaluation, sizing, execution, telemetry, and hedge handling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..context import RuntimeContext
from ..market.snapshot import MarketSnapshot
from ..risk import TradePolicy, PositionSizer, TradeIntent

logger = logging.getLogger("SwarmNode.TradeFlow")


class TradeFlowService:
    """
    Coordinates trading decisions and execution.

    Responsibilities:

    1. evaluate market conditions
    2. ask policy if trade allowed
    3. calculate position size
    4. execute trade
    5. update capital state
    6. publish telemetry
    7. perform hedge logic
    """

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

        self._policy = TradePolicy(ctx)
        self._sizer = PositionSizer(ctx)

    async def process(
        self,
        snapshot: MarketSnapshot,
    ) -> Optional[Dict[str, Any]]:

        """
        Main entrypoint.

        Called from node.main_loop().
        """

        intent = self._policy.evaluate(snapshot)

        if not intent.should_trade:
            logger.debug(
                "trade rejected: %s",
                intent.reason,
            )
            return None

        amount = self._sizer.size(
            intent,
            snapshot,
        )

        if amount <= 0:
            logger.debug("trade size <=0")
            return None

        return await self._execute(
            intent=intent,
            amount=amount,
        )

    async def _execute(
        self,
        intent: TradeIntent,
        amount: float,
    ) -> Optional[Dict[str, Any]]:

        symbol = intent.symbol
        side = intent.side

        prev_capital = self._ctx.capital

        trade_result = None

        try:

            trade_result = await self._ctx.executor.execute_order(
                symbol=symbol,
                side=side,
                amount=amount,
                price=intent.price,
                capital=self._ctx.capital,
            )

        except Exception as e:

            logger.exception(
                "trade execution failed"
            )

            trade_result = {
                "success":False,
                "status":str(e),
                "tx_hash":"",
            }

        self._apply_post_trade_capital(
            amount=amount,
            price=intent.price,
        )

        if (
            trade_result
            and trade_result.get("success")
        ):

            await self._publish_trade(
                trade_result,
                symbol,
                side,
                amount,
                prev_capital,
            )

            await self._handle_hedge(
                symbol=symbol,
                side=side,
                amount=amount,
            )

        return trade_result

    def _apply_post_trade_capital(
        self,
        amount: float,
        price: float,
    ) -> None:

        """
        Preserve current node.py behavior.

        This is still synthetic capital logic.
        Later real pnl can replace it.
        """

        simulated_return = (
            price
            * amount
            * 0.1
        )

        self._ctx.capital *= (
            1 + simulated_return
        )

        self._ctx.capital_manager.capital = (
            self._ctx.capital
        )

        self._ctx.capital_manager.apply_dq_delta(
            0.001
        )

    async def _publish_trade(
        self,
        trade_result: Dict[str,Any],
        symbol:str,
        side:str,
        amount:float,
        prev_capital:float,
    ) -> None:

        try:

            self._ctx.telemetry.update_impact(
                self._ctx.capital
            )

            await self._ctx.telemetry.trade(
                step=self._ctx.step_count,
                symbol=symbol,
                side=side,
                amount=amount,
                tx_hash=trade_result.get(
                    "tx_hash",
                    "",
                ),
                status=trade_result.get(
                    "status",
                    "unknown",
                ),
                capital_before=prev_capital,
                capital_after=self._ctx.capital,
                trace_id=self._ctx.trace_id,
            )

        except Exception:

            logger.exception(
                "telemetry publish failed"
            )

    async def _handle_hedge(
        self,
        symbol:str,
        side:str,
        amount:float,
    ) -> None:

        if (
            self._ctx.config.market_mode
            != "futures"
        ):
            return

        if not getattr(
            self._ctx.market_adapter,
            "hedge_enabled",
            False,
        ):
            return

        hedge_ratio = (
            self._ctx.config.hedge_ratio
        )

        hedge_amount = (
            abs(amount)
            * hedge_ratio
        )

        if hedge_amount <=0:
            return

        hedge_side = (
            "sell"
            if side=="buy"
            else "buy"
        )

        try:

            spot_adapter = (
                self._ctx.market_adapter.get_adapter(
                    symbol,
                    "spot",
                )
            )

            if not spot_adapter:
                return

            await spot_adapter.place_order(
                symbol,
                hedge_side,
                hedge_amount,
            )

            logger.info(
                "hedge placed"
            )

        except Exception:

            logger.exception(
                "hedge failed"
            )