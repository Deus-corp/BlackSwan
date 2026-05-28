"""Capital management and survival state helpers for swarm trading nodes."""

from __future__ import annotations

import logging
import math
from typing import Any, Final, Protocol, runtime_checkable

from swarm_config import config

logger: Final = logging.getLogger(__name__)


@runtime_checkable
class SurvivalEvaluatorProtocol(Protocol):
    """Expected interface for a survival evaluator."""

    dq: float
    liveness: float


class CapitalManager:
    """Manage node capital, burn rate, trade outcomes, and survival metrics."""

    __slots__ = ("capital", "burn_rate", "alert_threshold", "survival", "initial_capital", "realized_pnl")

    DEFAULT_CAPITAL: Final[float] = 1000.0

    def __init__(
        self,
        capital: float = DEFAULT_CAPITAL,
        *,
        burn_rate: float | None = None,
        alert_threshold: float | None = None,
    ) -> None:
        self.initial_capital = self._require_non_negative(capital, "capital")
        self.capital = self.initial_capital
        self.burn_rate = self._require_non_negative(
            getattr(config, "burn_rate", 0.0) if burn_rate is None else burn_rate,
            "burn_rate",
        )
        self.alert_threshold = self._require_non_negative(
            getattr(config, "capital_alert_threshold", 0.0) if alert_threshold is None else alert_threshold,
            "capital_alert_threshold",
        )
        self.survival: SurvivalEvaluatorProtocol | None = None
        self.realized_pnl = 0.0

    def set_survival(self, survival_evaluator: SurvivalEvaluatorProtocol) -> None:
        """Attach a SurvivalEvaluator-like object."""
        dq = self._require_unit_interval(getattr(survival_evaluator, "dq", None), "dq")
        liveness = self._require_unit_interval(getattr(survival_evaluator, "liveness", None), "liveness")

        survival_evaluator.dq = dq
        survival_evaluator.liveness = liveness
        self.survival = survival_evaluator

    def burn(self, multiplier: float = 1.0) -> float:
        """Deduct burn rate from capital and return deducted amount."""
        safe_multiplier = self._require_non_negative(multiplier, "multiplier")
        amount = min(self.capital, self.burn_rate * safe_multiplier)
        self.capital = max(0.0, self.capital - amount)

        logger.debug("Capital burn applied amount=%.6f capital=%.6f", amount, self.capital)
        return amount

    def apply_trade(self, result: dict[str, Any]) -> float:
        """Apply execution result to capital and return capital delta."""
        if not isinstance(result, dict):
            raise TypeError("result must be a dictionary")

        old_capital = self.capital

        if "new_capital" in result and result.get("new_capital") is not None:
            new_capital = self._require_non_negative(result.get("new_capital"), "new_capital")
            self.capital = new_capital
            delta = self.capital - old_capital
        else:
            delta = self._safe_float(result.get("capital_delta", result.get("pnl", 0.0)), 0.0)
            if not math.isfinite(delta):
                delta = 0.0
            self.capital = max(0.0, self.capital + delta)

        self.realized_pnl += delta

        logger.info(
            "Trade result applied status=%s success=%s delta=%.6f capital=%.6f",
            result.get("status"),
            result.get("success"),
            delta,
            self.capital,
        )
        return delta

    def deposit(self, amount: float) -> float:
        """Increase capital and return the new capital."""
        value = self._require_positive(amount, "amount")
        self.capital += value
        logger.info("Capital deposit amount=%.6f capital=%.6f", value, self.capital)
        return self.capital

    def withdraw(self, amount: float) -> float:
        """Decrease capital and return the new capital."""
        value = self._require_positive(amount, "amount")
        if value > self.capital:
            raise ValueError("withdraw amount exceeds current capital")

        self.capital -= value
        logger.info("Capital withdrawal amount=%.6f capital=%.6f", value, self.capital)
        return self.capital

    def is_alive(self) -> bool:
        """Return True when node has positive capital and liveness is positive."""
        if self.capital <= 0:
            return False
        if self.survival is not None and float(self.survival.liveness) <= 0:
            return False
        return True

    def needs_alert(self) -> bool:
        """Return True when capital is at or below alert threshold."""
        return self.alert_threshold > 0 and self.capital <= self.alert_threshold

    def health_snapshot(self) -> dict[str, float]:
        """Return current capital and survival metrics."""
        return {
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "realized_pnl": self.realized_pnl,
            "burn_rate": self.burn_rate,
            "alert_threshold": self.alert_threshold,
            "dq": float(self.survival.dq) if self.survival else 0.0,
            "liveness": float(self.survival.liveness) if self.survival else 1.0,
        }

    def apply_dq_delta(self, delta: float = 0.001) -> None:
        """Increment DQ metric on attached survival evaluator."""
        safe_delta = self._require_non_negative(delta, "delta")

        if self.survival is None:
            logger.warning("Attempted to apply DQ delta without SurvivalEvaluator.")
            return

        self.survival.dq = min(1.0, max(0.0, float(self.survival.dq) + safe_delta))
        logger.debug("DQ updated to %.6f", self.survival.dq)

    def apply_liveness_delta(self, delta: float) -> None:
        """Adjust liveness metric on attached survival evaluator."""
        if self.survival is None:
            logger.warning("Attempted to apply liveness delta without SurvivalEvaluator.")
            return

        safe_delta = self._safe_float(delta, 0.0)
        self.survival.liveness = min(1.0, max(0.0, float(self.survival.liveness) + safe_delta))
        logger.debug("Liveness updated to %.6f", self.survival.liveness)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @classmethod
    def _require_non_negative(cls, value: Any, name: str) -> float:
        number = cls._safe_float(value, float("nan"))
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{name} must be a non-negative finite number")
        return number

    @classmethod
    def _require_positive(cls, value: Any, name: str) -> float:
        number = cls._safe_float(value, float("nan"))
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{name} must be a positive finite number")
        return number

    @classmethod
    def _require_unit_interval(cls, value: Any, name: str) -> float:
        number = cls._safe_float(value, float("nan"))
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise ValueError(f"{name} must be in [0.0, 1.0]")
        return number