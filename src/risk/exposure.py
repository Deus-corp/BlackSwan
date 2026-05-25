"""
Exposure and position tracking system.

This module provides structured classes for managing trading positions and
tracking market exposure, including PnL monitoring and risk limit checks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Final, Literal, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Position:
    """
    Represents an immutable snapshot of an open trading position.

    Attributes:
        symbol: The unique ticker symbol of the asset.
        side: The trade direction, either 'long' or 'short'.
        amount: The total volume/quantity of the position.
        entry_price: The price at which the position was initiated.
    """
    symbol: str
    side: Literal["long", "short"]
    amount: float
    entry_price: float

    def unrealised_pnl(self, current_price: float) -> float:
        """
        Calculates the unrealised Profit & Loss for the position.

        Args:
            current_price: The current market price of the asset.

        Returns:
            The calculated unrealised PnL value.
        """
        if self.side == "long":
            return (current_price - self.entry_price) * self.amount
        return (self.entry_price - current_price) * self.amount


class ExposureManager:
    """
    Tracks active positions and enforces portfolio-level risk limits.

    Attributes:
        max_notional: Maximum allowed notional value for a single trade.
        max_daily_loss: Threshold for total daily loss before stopping trade activity.
    """

    def __init__(self, max_notional: float = 100_000.0, max_daily_loss: float = 5_000.0) -> None:
        self.max_notional: Final[float] = max_notional
        self.max_daily_loss: Final[float] = max_daily_loss
        self._positions: Dict[str, Position] = {}
        self.daily_pnl: float = 0.0
        logger.info(
            "ExposureManager initialized with max_notional=%f, max_daily_loss=%f",
            self.max_notional, self.max_daily_loss
        )

    @property
    def positions(self) -> Dict[str, Position]:
        """Returns the dictionary of currently tracked positions."""
        return self._positions

    def add_position(self, position: Position) -> None:
        """Records or updates an active position in the registry."""
        self._positions[position.symbol] = position
        logger.info(
            "Position updated for %s. Total active positions: %d",
            position.symbol, len(self._positions)
        )

    def close_position(self, symbol: str) -> Optional[Position]:
        """Removes an active position if it exists."""
        position = self._positions.pop(symbol, None)
        if position:
            logger.info(
                "Position closed for %s. Remaining: %d",
                symbol, len(self._positions)
            )
        else:
            logger.warning("Attempted to close non-existent position: %s", symbol)
        return position

    def pre_trade_check(self, symbol: str, action: str, amount: float, current_price: float) -> bool:
        """
        Validates if a proposed trade complies with risk limits.

        Args:
            symbol: Asset identifier.
            action: Intended market action (e.g., 'buy', 'sell').
            amount: Quantity to be traded.
            current_price: Current market price.

        Returns:
            bool: True if the trade is within risk limits, False otherwise.
        """
        notional = amount * current_price
        if notional > self.max_notional:
            logger.error("Notional limit exceeded for %s: %f > %f", symbol, notional, self.max_notional)
            return False

        if self.daily_pnl < -self.max_daily_loss:
            logger.error("Daily loss threshold breached: %f < %f", self.daily_pnl, -self.max_daily_loss)
            return False

        logger.debug("Pre-trade check passed for %s", symbol)
        return True

    def update_pnl(self, pnl: float) -> None:
        """Updates daily PnL and triggers critical logs if limits are violated."""
        self.daily_pnl += pnl
        logger.info("Daily PnL updated: %f. Cumulative: %f", pnl, self.daily_pnl)

        if self.daily_pnl < -self.max_daily_loss:
            logger.critical(
                "CRITICAL: Daily loss limit breached! Current: %f, Limit: %f",
                self.daily_pnl, -self.max_daily_loss
            )