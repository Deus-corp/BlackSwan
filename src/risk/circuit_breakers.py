"""
Framework for a simple risk management system (Circuit Breaker v2).

This module defines a basic circuit breaker that can halt trading based on
pre-defined risk limits, such as maximum daily loss.
"""
import logging
from typing import Any, Dict, Final

logger: Final = logging.getLogger(__name__)

class CircuitBreaker:
    """
    A basic circuit breaker for managing trading risks.

    It monitors daily PnL and can halt trading if a maximum daily loss
    threshold is breached. Includes pre-trade and post-trade checks.
    """
    __slots__ = ('max_daily_loss', 'max_slippage', 'daily_pnl', 'halted')

    def __init__(self, max_daily_loss: float = 5000.0, max_slippage: float = 0.02) -> None:
        """
        Initializes the CircuitBreaker with specified risk thresholds.

        Args:
            max_daily_loss: The maximum allowed daily loss (in currency units).
            max_slippage: The maximum allowed slippage ratio for a trade.

        Raises:
            ValueError: If `max_daily_loss` <= 0 or `max_slippage` < 0.
        """
        if max_daily_loss <= 0.0:
            raise ValueError("max_daily_loss must be a positive number.")
        if max_slippage < 0.0:
            raise ValueError("max_slippage must be a non-negative number.")

        self.max_daily_loss: Final[float] = max_daily_loss
        self.max_slippage: Final[float] = max_slippage
        self.daily_pnl: float = 0.0
        self.halted: bool = False
        logger.info(
            "CircuitBreaker initialized: loss_limit=%.2f, slippage_limit=%.2f",
            max_daily_loss, max_slippage
        )

    def pre_trade_check(self, signal: Dict[str, Any], portfolio: Dict[str, Any]) -> bool:
        """
        Performs checks before a trade is executed.

        Args:
            signal: The trading signal generated.
            portfolio: The current portfolio state.

        Returns:
            True if the trade is allowed, False if the breaker is halted.

        Raises:
            TypeError: If arguments are not dictionaries.
        """
        if not isinstance(signal, dict) or not isinstance(portfolio, dict):
            raise TypeError("Signal and portfolio must be provided as dictionaries.")

        if self.halted:
            logger.warning("Circuit breaker is active. Blocking order for: %s", signal.get('symbol', 'unknown'))
            return False

        return True

    def post_trade_check(self, fill: Dict[str, Any]) -> None:
        """
        Updates daily PnL and triggers circuit breaker if loss limits are exceeded.

        Args:
            fill: Information about the filled trade, expected to contain 'pnl'.

        Raises:
            TypeError: If `fill` is not a dictionary.
            ValueError: If 'pnl' is missing or not a valid number.
        """
        if not isinstance(fill, dict):
            raise TypeError("Fill information must be a dictionary.")

        try:
            pnl_val = fill.get('pnl', 0.0)
            pnl = float(pnl_val) if pnl_val is not None else 0.0
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid PnL value in fill data: {fill.get('pnl')}") from exc

        self.daily_pnl += pnl
        logger.debug("Post-trade update: PnL=%.2f, Daily Total=%.2f", pnl, self.daily_pnl)

        if self.daily_pnl < -self.max_daily_loss:
            self.halted = True
            logger.critical(
                "DAILY LOSS LIMIT BREACHED: %.2f < -%.2f. TRADING HALTED.",
                self.daily_pnl, self.max_daily_loss
            )

    def reset_daily(self) -> None:
        """
        Resets the daily PnL counter and clears the halted state.
        """
        self.daily_pnl = 0.0
        self.halted = False
        logger.info("Circuit breaker state reset for new session.")