"""Risk manager for trade and swarm operations."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Structured risk assessment result."""

    allowed: bool
    level: RiskLevel
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "level": self.level,
            "score": self.score,
            "reasons": list(self.reasons),
        }


class RiskManager:
    """Manage lightweight risk checks for trade and swarm operations."""

    DEFAULT_MAX_RISK_SCORE = 0.7
    DEFAULT_MAX_POSITION_FRACTION = 0.25
    DEFAULT_MAX_DAILY_LOSS_FRACTION = 0.05
    DEFAULT_MIN_CAPITAL = 0.0

    def __init__(
        self,
        *,
        max_risk_score: float = DEFAULT_MAX_RISK_SCORE,
        max_position_fraction: float = DEFAULT_MAX_POSITION_FRACTION,
        max_daily_loss_fraction: float = DEFAULT_MAX_DAILY_LOSS_FRACTION,
        min_capital: float = DEFAULT_MIN_CAPITAL,
    ) -> None:
        self.max_risk_score = self._clamp(self._safe_float(max_risk_score, self.DEFAULT_MAX_RISK_SCORE), 0.0, 1.0)
        self.max_position_fraction = self._clamp(
            self._safe_float(max_position_fraction, self.DEFAULT_MAX_POSITION_FRACTION),
            0.0,
            1.0,
        )
        self.max_daily_loss_fraction = self._clamp(
            self._safe_float(max_daily_loss_fraction, self.DEFAULT_MAX_DAILY_LOSS_FRACTION),
            0.0,
            1.0,
        )
        self.min_capital = max(0.0, self._safe_float(min_capital, self.DEFAULT_MIN_CAPITAL))

    def assess(self, *args: Any, **kwargs: Any) -> bool:
        """Compatibility boolean risk check."""
        return self.assess_details(*args, **kwargs).allowed

    def assess_details(self, *args: Any, **kwargs: Any) -> RiskAssessment:
        """Return detailed risk assessment.

        Accepted inputs:
        - assess_details(signal: dict, portfolio: dict)
        - assess_details(signal=<dict>, portfolio=<dict>)
        - assess_details(capital=..., notional=..., daily_pnl=..., execution_enabled=...)
        """
        signal = kwargs.get("signal")
        portfolio = kwargs.get("portfolio")

        if len(args) >= 1 and isinstance(args[0], dict):
            signal = args[0]
        if len(args) >= 2 and isinstance(args[1], dict):
            portfolio = args[1]

        signal = signal if isinstance(signal, dict) else {}
        portfolio = portfolio if isinstance(portfolio, dict) else {}

        capital = max(
            0.0,
            self._safe_float(
                kwargs.get("capital", portfolio.get("capital", portfolio.get("equity", portfolio.get("balance")))),
                0.0,
            ),
        )
        daily_pnl = self._safe_float(kwargs.get("daily_pnl", portfolio.get("daily_pnl")), 0.0)
        notional = max(0.0, self._safe_float(kwargs.get("notional"), self._signal_notional(signal)))

        execution_enabled = kwargs.get("execution_enabled", signal.get("execution_enabled", False))
        dry_run = kwargs.get("dry_run", signal.get("dry_run", True))

        reasons: list[str] = []
        score = 0.0

        if capital < self.min_capital:
            reasons.append(f"capital_below_min:{capital:.4f}<{self.min_capital:.4f}")
            score += 0.35

        if capital > 0 and notional > capital * self.max_position_fraction:
            reasons.append(f"position_too_large:{notional / capital:.4f}>{self.max_position_fraction:.4f}")
            score += 0.35

        if capital > 0 and daily_pnl < -(capital * self.max_daily_loss_fraction):
            reasons.append(
                f"daily_loss_too_large:{daily_pnl:.4f}<-{capital * self.max_daily_loss_fraction:.4f}"
            )
            score += 0.45

        if self._truthy(execution_enabled) and self._truthy(dry_run):
            reasons.append("execution_enabled_conflicts_with_dry_run")
            score += 0.2

        explicit_score = kwargs.get("risk_score", signal.get("risk_score"))
        if explicit_score is not None:
            explicit = self._clamp(self._safe_float(explicit_score, 0.0), 0.0, 1.0)
            score = max(score, explicit)
            if explicit > self.max_risk_score:
                reasons.append(f"explicit_risk_score_too_high:{explicit:.4f}>{self.max_risk_score:.4f}")

        score = self._clamp(score, 0.0, 1.0)
        level = self._level(score)
        allowed = score <= self.max_risk_score and not reasons_with_hard_block(reasons)

        if not allowed:
            logger.warning("Risk assessment blocked operation: level=%s score=%.3f reasons=%s", level, score, reasons)

        return RiskAssessment(
            allowed=allowed,
            level=level,
            score=score,
            reasons=reasons,
        )

    @staticmethod
    def _signal_notional(signal: dict[str, Any]) -> float:
        explicit = signal.get("notional", signal.get("value"))
        if explicit is not None:
            return RiskManager._safe_float(explicit, 0.0)

        amount = RiskManager._safe_float(signal.get("amount", signal.get("qty", signal.get("quantity"))), 0.0)
        price = RiskManager._safe_float(signal.get("price"), 0.0)
        return amount * price

    @staticmethod
    def _level(score: float) -> RiskLevel:
        if score >= 0.85:
            return "critical"
        if score >= 0.6:
            return "high"
        if score >= 0.3:
            return "medium"
        return "low"

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "enabled", "on"}

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))


def reasons_with_hard_block(reasons: list[str]) -> bool:
    """Return True for risk reasons that should block even when aggregate score is low."""
    hard_prefixes = (
        "daily_loss_too_large:",
        "position_too_large:",
        "capital_below_min:",
        "explicit_risk_score_too_high:",
    )
    return any(any(reason.startswith(prefix) for prefix in hard_prefixes) for reason in reasons)