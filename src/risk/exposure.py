"""
Exposure and position tracking system (stub).

This module provides foundational classes for managing trading positions and
tracking overall market exposure. It is designed to be integrated with a
full risk engine for enforcing sophisticated risk limits such as maximum notional
per asset, daily loss limits, and correlation-based exposure constraints.
Currently, it functions as a basic tracking system with stubbed risk checks.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Position:
    """
    Represents an open trading position in a single asset.
    """

    def __init__(self, symbol: str, side: str, amount: float, entry_price: float) -> None:
        """
        Initializes a new Position.

        Args:
            symbol (str): The trading symbol of the asset (e.g., 'AAPL', 'BTC/USD').
            side (str): The side of the position ('long' or 'short').
            amount (float): The quantity or size of the position.
            entry_price (float): The average price at which the position was opened.
        """
        self.symbol: str = symbol
        self.side: str = side
        self.amount: float = amount
        self.entry_price: float = entry_price
        logger.debug(f"Position opened: {self.symbol}, {self.side}, Amount: {self.amount}, Entry: {self.entry_price}")

    def unrealised_pnl(self, current_price: float) -> float:
        """
        Calculates the unrealised Profit & Loss for the position.

        Stub: Always returns 0.0 for now. In a real implementation, this
        would calculate PnL based on `current_price` and `entry_price`.

        Args:
            current_price (float): The current market price of the asset.

        Returns:
            float: The unrealised PnL.
        """
        # In a real system, this would be:
        # if self.side == 'long':
        #     return (current_price - self.entry_price) * self.amount
        # else: # 'short'
        #     return (self.entry_price - current_price) * self.amount
        return 0.0


class ExposureManager:
    """
    Tracks current open positions and manages overall exposure, including daily PnL.

    This manager provides methods to add, close, and check positions against
    pre-defined risk limits. Currently, most checks are stubs that always allow
    trades, but it tracks daily PnL and alerts if maximum daily loss is breached.
    """

    def __init__(self, max_notional: float = 100_000.0, max_daily_loss: float = 5_000.0) -> None:
        """
        Initializes the ExposureManager with global risk limits.

        Args:
            max_notional (float): The maximum notional value allowed for any single position.
                                  (Currently not actively enforced).
            max_daily_loss (float): The maximum aggregate daily loss allowed across all positions.
                                    If `daily_pnl` drops below `-max_daily_loss`, an error is logged.
        """
        self.max_notional: float = max_notional
        self.max_daily_loss: float = max_daily_loss
        self.positions: Dict[str, Position] = {}
        self.daily_pnl: float = 0.0
        logger.info(f"ExposureManager initialised (stub) with max_notional={max_notional}, max_daily_loss={max_daily_loss}")

    def add_position(self, position: Position) -> None:
        """
        Records a new or updates an existing open position.

        Args:
            position (Position): The Position object to add.
        """
        self.positions[position.symbol] = position
        logger.info(f"Position added/updated for {position.symbol}. Current positions: {len(self.positions)}")

    def close_position(self, symbol: str) -> Optional[Position]:
        """
        Closes and removes the position for the given symbol.

        Args:
            symbol (str): The trading symbol of the position to close.

        Returns:
            Optional[Position]: The closed Position object if found, otherwise None.
        """
        if symbol in self.positions:
            position = self.positions.pop(symbol)
            logger.info(f"Position closed for {symbol}. Remaining positions: {len(self.positions)}")
            return position
        logger.warning(f"Attempted to close position for {symbol}, but no such position was found.")
        return None

    def pre_trade_check(self, symbol: str, action: str, amount: float, current_price: float) -> bool:
        """
        Checks whether a proposed trade is within overall risk limits.

        Stub: Always returns True. In a full implementation, this would involve
        complex calculations based on `max_notional`, `max_daily_loss`,
        portfolio correlation, etc.

        Args:
            symbol (str): The symbol of the asset for the proposed trade.
            action (str): The intended action ('buy' or 'sell').
            amount (float): The quantity for the proposed trade.
            current_price (float): The current market price of the asset.

        Returns:
            bool: True if the trade is allowed, False otherwise.
        """
        logger.debug(f"Pre-trade check for {action} {amount} of {symbol} @ {current_price} (stub: always True)")
        # Future implementations would check against:
        # - Max notional exposure per asset
        # - Max portfolio-level notional exposure
        # - Correlation-based limits
        # - Current PnL vs. max_daily_loss (if not managed by a separate circuit breaker)
        return True

    def update_pnl(self, pnl: float) -> None:
        """
        Updates the total daily PnL and checks if the daily loss limit is breached.

        Args:
            pnl (float): The PnL (profit or loss) incurred from a trade or position update.
        """
        self.daily_pnl += pnl
        logger.info(f"Daily PnL updated: {pnl}. Current total daily PnL: {self.daily_pnl:.2f}")

        if self.daily_pnl < -self.max_daily_loss:
            logger.error(f"Daily loss limit reached! Further trading should be halted. Current daily PnL: {self.daily_pnl:.2f} (Limit: {-self.max_daily_loss:.2f})")