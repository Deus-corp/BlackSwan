"""Risk circuit breakers for trading execution safety."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Final

logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CircuitBreakerDecision:
    """Pre-trade circuit breaker decision."""

    allowed: bool
    reason: str = ""
    details: dict[str, Any] | None = None


class CircuitBreaker:
    """Simple risk circuit breaker for daily loss, slippage, and exposure checks."""

    __slots__ = (
        "max_daily_loss",
        "max_slippage",
        "max_position_fraction",
        "daily_pnl",
        "halted",
        "halt_reason",
    )

    DEFAULT_MAX_POSITION_FRACTION: Final[float] = 0.25

    def __init__(
        self,
        max_daily_loss: float = 5000.0,
        max_slippage: float = 0.02,
        *,
        max_position_fraction: float = DEFAULT_MAX_POSITION_FRACTION,
    ) -> None:
        self.max_daily_loss = self._require_positive(max_daily_loss, "max_daily_loss")
        self.max_slippage = self._require_non_negative(max_slippage, "max_slippage")
        self.max_position_fraction = min(
            1.0,
            self._require_positive(max_position_fraction, "max_position_fraction"),
        )

        self.daily_pnl = 0.0
        self.halted = False
        self.halt_reason = ""

        logger.info(
            "CircuitBreaker initialized: max_daily_loss=%.2f max_slippage=%.4f max_position_fraction=%.4f",
            self.max_daily_loss,
            self.max_slippage,
            self.max_position_fraction,
        )

    def pre_trade_check(self, signal: dict[str, Any], portfolio: dict[str, Any]) -> bool:
        """Return True when the trade is allowed."""
        return self.pre_trade_decision(signal, portfolio).allowed

    def pre_trade_decision(
        self,
        signal: dict[str, Any],
        portfolio: dict[str, Any],
    ) -> CircuitBreakerDecision:
        """Return detailed pre-trade circuit breaker decision."""
        if not isinstance(signal, dict):
            raise TypeError("signal must be a dictionary")
        if not isinstance(portfolio, dict):
            raise TypeError("portfolio must be a dictionary")

        symbol = str(signal.get("symbol", "unknown") or "unknown")

        if self.halted:
            reason = self.halt_reason or "circuit_breaker_halted"
            logger.warning("Circuit breaker active. Blocking order for %s: %s", symbol, reason)
            return CircuitBreakerDecision(False, reason, {"symbol": symbol})

        slippage = self._safe_float(signal.get("slippage", signal.get("expected_slippage")), 0.0)
        if slippage > self.max_slippage:
            reason = f"slippage_exceeds_limit:{slippage:.6f}>{self.max_slippage:.6f}"
            logger.warning("Blocking %s due to %s", symbol, reason)
            return CircuitBreakerDecision(False, reason, {"symbol": symbol, "slippage": slippage})

        capital = max(
            0.0,
            self._safe_float(
                portfolio.get("capital", portfolio.get("equity", portfolio.get("balance"))),
                0.0,
            ),
        )
        notional = self._signal_notional(signal)

        if capital > 0 and notional > capital * self.max_position_fraction:
            reason = (
                f"position_fraction_exceeds_limit:"
                f"{notional / capital:.6f}>{self.max_position_fraction:.6f}"
            )
            logger.warning("Blocking %s due to %s", symbol, reason)
            return CircuitBreakerDecision(
                False,
                reason,
                {
                    "symbol": symbol,
                    "notional": notional,
                    "capital": capital,
                    "max_position_fraction": self.max_position_fraction,
                },
            )

        return CircuitBreakerDecision(True, "allowed", {"symbol": symbol})

    def post_trade_check(self, fill: dict[str, Any]) -> None:
        """Update daily PnL and halt if daily loss limit is breached."""
        if not isinstance(fill, dict):
            raise TypeError("fill must be a dictionary")

        pnl = self._safe_float(fill.get("pnl", fill.get("pnl_delta")), 0.0)
        self.daily_pnl += pnl

        logger.debug("Post-trade PnL update: pnl=%.4f daily_pnl=%.4f", pnl, self.daily_pnl)

        if self.daily_pnl <= -self.max_daily_loss:
            self.trip(f"daily_loss_limit_breached:{self.daily_pnl:.4f}<=-{self.max_daily_loss:.4f}")

    def trip(self, reason: str = "manual_trip") -> None:
        """Manually activate the circuit breaker."""
        self.halted = True
        self.halt_reason = str(reason or "manual_trip")
        logger.critical("TRADING HALTED: %s", self.halt_reason)

    def reset_daily(self) -> None:
        """Reset daily PnL and clear halted state."""
        self.daily_pnl = 0.0
        self.halted = False
        self.halt_reason = ""
        logger.info("Circuit breaker state reset for new session.")

    def to_dict(self) -> dict[str, Any]:
        """Return serializable circuit breaker state."""
        return {
            "max_daily_loss": self.max_daily_loss,
            "max_slippage": self.max_slippage,
            "max_position_fraction": self.max_position_fraction,
            "daily_pnl": self.daily_pnl,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
        }

    def _signal_notional(self, signal: dict[str, Any]) -> float:
        explicit = signal.get("notional", signal.get("value"))
        if explicit is not None:
            return max(0.0, self._safe_float(explicit, 0.0))

        amount = max(0.0, self._safe_float(signal.get("amount", signal.get("qty", signal.get("quantity"))), 0.0))
        price = max(0.0, self._safe_float(signal.get("price"), 0.0))
        return amount * price

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        return number if math.isfinite(number) else default

    @classmethod
    def _require_positive(cls, value: Any, name: str) -> float:
        number = cls._safe_float(value, float("nan"))
        if not math.isfinite(number) or number <= 0.0:
            raise ValueError(f"{name} must be a positive finite number")
        return number

    @classmethod
    def _require_non_negative(cls, value: Any, name: str) -> float:
        number = cls._safe_float(value, float("nan"))
        if not math.isfinite(number) or number < 0.0:
            raise ValueError(f"{name} must be a non-negative finite number")
        return number