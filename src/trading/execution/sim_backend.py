"""Execution backend implementation for simulated trading environments."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any

from .backend import ExecutionBackend, ExecutionResult, OrderSide, rejected_result


class SimExecutionBackend(ExecutionBackend):
    """Backend for deterministic/stochastic simulated order execution."""

    DEFAULT_MIN_FLUCTUATION = -0.01
    DEFAULT_MAX_FLUCTUATION = 0.02

    def __init__(
        self,
        *,
        min_fluctuation: float = DEFAULT_MIN_FLUCTUATION,
        max_fluctuation: float = DEFAULT_MAX_FLUCTUATION,
        seed: int | None = None,
        deterministic: bool = False,
    ) -> None:
        self.min_fluctuation = float(min_fluctuation)
        self.max_fluctuation = float(max_fluctuation)
        self.deterministic = bool(deterministic)
        self._rng = random.Random(seed)

        if self.min_fluctuation > self.max_fluctuation:
            raise ValueError("min_fluctuation cannot be greater than max_fluctuation")

    async def execute_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        price: float,
        capital: float,
    ) -> ExecutionResult:
        """Simulate order execution by applying bounded PnL fluctuation to trade value."""
        clean_symbol = str(symbol or "").strip()
        clean_side = str(side or "").strip().lower()
        capital_value = self._safe_float(capital, 0.0)

        if not clean_symbol:
            return rejected_result(capital_value, "symbol_required")
        if clean_side not in {"buy", "sell"}:
            return rejected_result(capital_value, f"unsupported_side:{side}")

        amount_value = self._safe_positive(amount)
        price_value = self._safe_positive(price)
        if amount_value is None:
            return rejected_result(capital_value, "amount_must_be_positive")
        if price_value is None:
            return rejected_result(capital_value, "price_must_be_positive")

        trade_value = price_value * amount_value
        fluctuation = self._fluctuation(clean_symbol, clean_side, amount_value, price_value, capital_value)
        capital_adjustment = trade_value * fluctuation

        return {
            "success": True,
            "new_capital": capital_value + capital_adjustment,
            "tx_hash": None,
            "status": "simulated",
            "error": None,
        }

    def _fluctuation(self, symbol: str, side: str, amount: float, price: float, capital: float) -> float:
        if not self.deterministic:
            return self._rng.uniform(self.min_fluctuation, self.max_fluctuation)

        source = f"{symbol}|{side}|{amount:.12f}|{price:.12f}|{capital:.12f}"
        digest = hashlib.sha256(source.encode("utf-8")).digest()
        unit = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
        return self.min_fluctuation + unit * (self.max_fluctuation - self.min_fluctuation)

    @staticmethod
    def _safe_positive(value: Any) -> float | None:
        number = SimExecutionBackend._safe_float(value, float("nan"))
        if not math.isfinite(number) or number <= 0:
            return None
        return number

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default