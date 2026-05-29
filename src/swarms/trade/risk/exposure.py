"""Exposure and position tracking system."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Final, Literal, Optional

logger = logging.getLogger(__name__)

PositionSide = Literal["long", "short"]


@dataclass(frozen=True, slots=True)
class Position:
    """Immutable snapshot of an open trading position."""

    symbol: str
    side: PositionSide
    amount: float
    entry_price: float

    def __post_init__(self) -> None:
        clean_symbol = str(self.symbol or "").strip()
        if not clean_symbol:
            raise ValueError("symbol cannot be empty")
        if self.side not in {"long", "short"}:
            raise ValueError("side must be 'long' or 'short'")
        if not math.isfinite(float(self.amount)) or float(self.amount) <= 0:
            raise ValueError("amount must be a positive finite number")
        if not math.isfinite(float(self.entry_price)) or float(self.entry_price) <= 0:
            raise ValueError("entry_price must be a positive finite number")

        object.__setattr__(self, "symbol", clean_symbol)
        object.__setattr__(self, "amount", float(self.amount))
        object.__setattr__(self, "entry_price", float(self.entry_price))

    @property
    def notional(self) -> float:
        return self.amount * self.entry_price

    def unrealised_pnl(self, current_price: float) -> float:
        """Calculate unrealised PnL at current market price."""
        price = _require_positive(current_price, "current_price")
        if self.side == "long":
            return (price - self.entry_price) * self.amount
        return (self.entry_price - price) * self.amount

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "entry_price": self.entry_price,
            "notional": self.notional,
        }


class ExposureManager:
    """Track active positions and enforce portfolio-level risk limits."""

    def __init__(self, max_notional: float = 100_000.0, max_daily_loss: float = 5_000.0) -> None:
        self.max_notional: Final[float] = _require_positive(max_notional, "max_notional")
        self.max_daily_loss: Final[float] = _require_positive(max_daily_loss, "max_daily_loss")
        self._positions: dict[str, Position] = {}
        self.daily_pnl = 0.0

        logger.info(
            "ExposureManager initialized max_notional=%.2f max_daily_loss=%.2f",
            self.max_notional,
            self.max_daily_loss,
        )

    @property
    def positions(self) -> dict[str, Position]:
        """Return a shallow copy of currently tracked positions."""
        return dict(self._positions)

    @property
    def total_entry_notional(self) -> float:
        return sum(position.notional for position in self._positions.values())

    @property
    def halted(self) -> bool:
        return self.daily_pnl <= -self.max_daily_loss

    def add_position(self, position: Position) -> None:
        """Record or replace an active position."""
        if not isinstance(position, Position):
            raise TypeError("position must be a Position instance")

        if position.notional > self.max_notional:
            raise ValueError(
                f"position notional exceeds limit: {position.notional:.4f} > {self.max_notional:.4f}"
            )

        self._positions[position.symbol] = position
        logger.info("Position updated symbol=%s active_positions=%d", position.symbol, len(self._positions))

    def close_position(self, symbol: str) -> Optional[Position]:
        """Remove and return an active position if it exists."""
        clean_symbol = str(symbol or "").strip()
        if not clean_symbol:
            raise ValueError("symbol cannot be empty")

        position = self._positions.pop(clean_symbol, None)
        if position is None:
            logger.warning("Attempted to close non-existent position: %s", clean_symbol)
            return None

        logger.info("Position closed symbol=%s remaining_positions=%d", clean_symbol, len(self._positions))
        return position

    def pre_trade_check(self, symbol: str, action: str, amount: float, current_price: float) -> bool:
        """Return True when a proposed trade complies with exposure limits."""
        clean_symbol = str(symbol or "").strip()
        clean_action = str(action or "").strip().lower()
        trade_amount = _require_positive(amount, "amount")
        price = _require_positive(current_price, "current_price")

        if not clean_symbol:
            raise ValueError("symbol cannot be empty")
        if clean_action not in {"buy", "sell", "long", "short", "close"}:
            raise ValueError("action must be one of: buy, sell, long, short, close")

        notional = trade_amount * price

        if notional > self.max_notional:
            logger.error("Notional limit exceeded for %s: %.4f > %.4f", clean_symbol, notional, self.max_notional)
            return False

        if self.halted:
            logger.error("Daily loss threshold breached: %.4f <= -%.4f", self.daily_pnl, self.max_daily_loss)
            return False

        logger.debug("Pre-trade check passed symbol=%s action=%s notional=%.4f", clean_symbol, clean_action, notional)
        return True

    def update_pnl(self, pnl: float) -> None:
        """Update daily realized PnL."""
        pnl_value = _safe_float(pnl, float("nan"))
        if not math.isfinite(pnl_value):
            raise ValueError("pnl must be a finite number")

        self.daily_pnl += pnl_value
        logger.info("Daily PnL updated pnl=%.4f cumulative=%.4f", pnl_value, self.daily_pnl)

        if self.halted:
            logger.critical(
                "CRITICAL: Daily loss limit breached. current=%.4f limit=-%.4f",
                self.daily_pnl,
                self.max_daily_loss,
            )

    def unrealised_pnl(self, prices: dict[str, float]) -> float:
        """Calculate total unrealised PnL from a symbol->price mapping."""
        if not isinstance(prices, dict):
            raise TypeError("prices must be a dictionary")

        total = 0.0
        for symbol, position in self._positions.items():
            if symbol not in prices:
                continue
            total += position.unrealised_pnl(prices[symbol])
        return total

    def exposure_by_symbol(self) -> dict[str, float]:
        """Return entry notional exposure by symbol."""
        return {symbol: position.notional for symbol, position in self._positions.items()}

    def to_dict(self) -> dict[str, Any]:
        """Return serializable exposure state."""
        return {
            "max_notional": self.max_notional,
            "max_daily_loss": self.max_daily_loss,
            "daily_pnl": self.daily_pnl,
            "halted": self.halted,
            "total_entry_notional": self.total_entry_notional,
            "positions": {symbol: position.to_dict() for symbol, position in self._positions.items()},
        }

    def reset_daily(self) -> None:
        """Reset only daily realized PnL."""
        self.daily_pnl = 0.0
        logger.info("ExposureManager daily PnL reset.")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _require_positive(value: Any, name: str) -> float:
    number = _safe_float(value, float("nan"))
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return number