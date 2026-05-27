"""Generic stochastic environment primitives for BlackSwan simulations.

Historically this file contained only a market GBM model. The class name
`MarketEnvironment` and methods `step()` / `get_state()` are preserved for
current runtime compatibility, but the implementation is now suitable as a
generic scalar environment for autonomous-swarm experiments.

Use cases:
- market price simulation,
- resource/energy dynamics,
- synthetic risk signal generation,
- stress-test worlds for swarm policy evaluation.
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from typing import Any, Literal, Optional, TypedDict


class MarketState(TypedDict, total=False):
    """State emitted by MarketEnvironment."""

    price: float
    value: float
    volatility_estimate: float
    drift: float
    step: int
    timestamp: float
    regime: str


RegimeName = Literal["normal", "shock", "recovery"]


class MarketEnvironment:
    """Stochastic scalar environment with market-compatible API."""

    __slots__ = (
        "volatility",
        "drift",
        "lookback_period",
        "prices",
        "values",
        "min_value",
        "max_value",
        "shock_probability",
        "shock_scale",
        "regime",
        "step_count",
        "_history",
        "_rng",
    )

    def __init__(
        self,
        volatility: float = 0.02,
        drift: float = 0.0,
        lookback_period: int = 100,
        *,
        initial_price: float = 1.0,
        min_value: float = 1e-9,
        max_value: float = 1e12,
        shock_probability: float = 0.0,
        shock_scale: float = 3.0,
        seed: Optional[int] = None,
    ) -> None:
        if volatility < 0:
            raise ValueError("volatility must be non-negative")
        if lookback_period <= 0:
            raise ValueError("lookback_period must be positive")
        if initial_price <= 0 or not math.isfinite(initial_price):
            raise ValueError("initial_price must be a positive finite number")
        if min_value <= 0 or max_value <= min_value:
            raise ValueError("invalid min_value/max_value bounds")

        self.volatility = float(volatility)
        self.drift = float(drift)
        self.lookback_period = int(lookback_period)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.shock_probability = max(0.0, min(1.0, float(shock_probability)))
        self.shock_scale = max(1.0, float(shock_scale))
        self.regime: RegimeName = "normal"
        self.step_count = 0

        self._rng = random.Random(seed)
        self._history: deque[float] = deque(maxlen=self.lookback_period + 1)

        initial = self._clamp_value(initial_price)
        self.values: list[float] = [initial]
        self.prices: list[float] = self.values

        self._history.append(initial)

    def step(self) -> float:
        """Advance environment by one step and return the new value/price."""
        state = self.step_state()
        return float(state["price"])

    def step_state(self) -> MarketState:
        """Advance environment by one step and return full state."""
        last_value = self.values[-1]
        regime = self._select_regime()
        scale = self.volatility * (self.shock_scale if regime == "shock" else 1.0)

        if regime == "recovery":
            effective_drift = abs(self.drift) + self.volatility * 0.25
        elif regime == "shock":
            effective_drift = self.drift - self.volatility * self.shock_scale * 0.25
        else:
            effective_drift = self.drift

        # Geometric-style multiplicative step. This keeps value positive and works
        # for prices/resources alike.
        random_component = self._rng.gauss(0.0, scale)
        log_return = effective_drift - 0.5 * (scale**2) + random_component
        new_value = last_value * math.exp(log_return)
        new_value = self._clamp_value(new_value)

        self.values.append(new_value)
        self._history.append(new_value)
        self.step_count += 1
        self.regime = regime

        return self.get_state()

    def get_state(self) -> MarketState:
        """Return current market-compatible state."""
        current_value = self.values[-1]
        return {
            "price": current_value,
            "value": current_value,
            "volatility_estimate": self.realized_volatility(),
            "drift": self.drift,
            "step": self.step_count,
            "timestamp": time.time(),
            "regime": self.regime,
        }

    def realized_volatility(self) -> float:
        """Estimate realized volatility from recent returns."""
        values = list(self._history)

        if len(values) < 2:
            return self.volatility

        returns: list[float] = []

        for previous, current in zip(values, values[1:]):
            if previous <= 0:
                continue
            returns.append((current - previous) / previous)

        if not returns:
            return self.volatility

        mean_return = sum(returns) / len(returns)
        variance = sum((item - mean_return) ** 2 for item in returns) / len(returns)
        return math.sqrt(max(0.0, variance))

    def reset(self, initial_price: float = 1.0) -> None:
        """Reset environment history."""
        if initial_price <= 0 or not math.isfinite(initial_price):
            raise ValueError("initial_price must be a positive finite number")

        initial = self._clamp_value(initial_price)
        self.values.clear()
        self.values.append(initial)
        self._history.clear()
        self._history.append(initial)
        self.step_count = 0
        self.regime = "normal"

    def inject_shock(self, multiplier: float) -> MarketState:
        """Apply an explicit external shock and return state."""
        factor = float(multiplier)
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("shock multiplier must be positive and finite")

        new_value = self._clamp_value(self.values[-1] * factor)
        self.values.append(new_value)
        self._history.append(new_value)
        self.step_count += 1
        self.regime = "shock"
        return self.get_state()

    def _select_regime(self) -> RegimeName:
        if self.shock_probability > 0 and self._rng.random() < self.shock_probability:
            return "shock"

        if self.regime == "shock" and self._rng.random() < 0.35:
            return "recovery"

        return "normal"

    def _clamp_value(self, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError(f"environment generated non-finite value: {value}")
        return max(self.min_value, min(self.max_value, float(value)))


# Backward-compatible alias for future generic imports.
ScalarEnvironment = MarketEnvironment