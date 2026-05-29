"""Legacy MVP-compatible capital manager.

This module preserves old lab_swarm_demo test semantics while the canonical
trade capital manager lives in src.swarms.trade.domain.capital.
"""

from __future__ import annotations

from typing import Any


class CapitalManager:
    """Small legacy capital manager used by old decomposition/unit tests."""

    def __init__(
        self,
        capital: float = 1000.0,
        burn_rate: float = 1.0,
        min_capital: float = 1.0,
    ) -> None:
        self.capital = float(capital)
        self.initial_capital = float(capital)
        self.burn_rate = float(burn_rate)
        self.min_capital = float(min_capital)
        self.survival: Any = None
        self.last_dq_delta = 0.0

    def burn(self, amount: float | None = None) -> float:
        burn_amount = self.burn_rate if amount is None else float(amount)
        self.capital = max(0.0, self.capital - max(0.0, burn_amount))
        return self.capital

    def is_alive(self) -> bool:
        return self.capital >= self.min_capital

    def health_snapshot(self) -> dict[str, Any]:
        dq = float(getattr(self.survival, "dq", 0.0) or 0.0)
        liveness = float(getattr(self.survival, "liveness", 1.0) or 0.0)

        return {
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "min_capital": self.min_capital,
            "is_alive": self.is_alive(),
            "dq": dq,
            "liveness": liveness,
            "last_dq_delta": self.last_dq_delta,
        }

    def set_survival(self, survival: Any) -> None:
        self.survival = survival

    def apply_dq_delta(self, delta: float) -> float:
        safe_delta = float(delta)
        self.last_dq_delta = safe_delta

        if self.survival is not None and hasattr(self.survival, "dq"):
            current = float(getattr(self.survival, "dq", 0.0) or 0.0)
            setattr(self.survival, "dq", current + safe_delta)
            return float(getattr(self.survival, "dq", 0.0) or 0.0)

        return safe_delta