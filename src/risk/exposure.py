# src/risk/exposure.py
"""
Exposure and position tracking (stub).
Will later be integrated with the risk engine to enforce:
- Maximum notional per asset.
- Maximum daily loss.
- Correlation-based exposure limits.
- Portfolio-level risk checks before trade execution.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Position:
    """Represents an open position in a single asset."""

    def __init__(self, symbol: str, side: str, amount: float, entry_price: float):
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.entry_price = entry_price

    def unrealised_pnl(self, current_price: float) -> float:
        """Stub: always returns 0."""
        return 0.0


class ExposureManager:
    """
    Tracks current positions and enforces risk limits.
    Currently a stub that always allows trades.
    """

    def __init__(self, max_notional: float = 100_000.0, max_daily_loss: float = 5_000.0):
        self.max_notional = max_notional
        self.max_daily_loss = max_daily_loss
        self.positions: dict[str, Position] = {}
        self.daily_pnl = 0.0
        logger.info("ExposureManager initialised (stub)")

    def add_position(self, position: Position) -> None:
        """Record a new position."""
        self.positions[position.symbol] = position

    def close_position(self, symbol: str) -> Position | None:
        """Close and return the position for the given symbol."""
        return self.positions.pop(symbol, None)

    def pre_trade_check(self, symbol: str, action: str, amount: float, current_price: float) -> bool:
        """
        Check whether a proposed trade is within risk limits.
        Stub always returns True.
        """
        return True

    def update_pnl(self, pnl: float) -> None:
        """Update daily PnL and check if loss limits are breached."""
        self.daily_pnl += pnl
        if self.daily_pnl < -self.max_daily_loss:
            logger.error("Daily loss limit reached! Further trading should be halted.")