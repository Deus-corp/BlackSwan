"""Generic simulation agents for autonomous-system experiments.

Historically this module defined financial agents only. The public names
`BaseAgent`, `KellyAgent`, and `RandomAgent` are preserved for compatibility,
but the model is now framed around generic resources and action exposure.

A simulation agent:
- owns resources/capital,
- decides an action intensity in [-max_risk, max_risk],
- updates resources from an environment return/reward signal,
- records history for later analysis.
"""

from __future__ import annotations

import math
import random
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Final, Mapping, Optional, TypedDict


class MarketState(TypedDict, total=False):
    """Market-compatible state accepted by legacy agents."""

    volatility_estimate: float
    price: float
    value: float
    surprise: float
    risk: float
    reward_estimate: float


@dataclass(slots=True)
class AgentSnapshot:
    """Serializable agent state snapshot."""

    capital: float
    initial_capital: float
    max_risk: float
    total_return: float
    steps: int
    last_action: float
    last_reward: float
    mean_return: float
    volatility: float


class BaseAgent(ABC):
    """Abstract resource-owning simulation agent."""

    __slots__ = (
        "initial_capital",
        "capital",
        "max_risk",
        "history",
        "action_history",
        "return_history",
        "last_action",
        "last_reward",
        "_rng",
    )

    def __init__(self, capital: float, max_risk: float = 0.02, *, seed: Optional[int] = None) -> None:
        if not math.isfinite(float(capital)) or float(capital) <= 0:
            raise ValueError("capital must be a positive finite number")
        if not math.isfinite(float(max_risk)) or not (0.0 <= float(max_risk) <= 1.0):
            raise ValueError("max_risk must be in [0, 1]")

        self.initial_capital: Final[float] = float(capital)
        self.capital: float = float(capital)
        self.max_risk: Final[float] = float(max_risk)
        self.history: list[float] = [self.capital]
        self.action_history: list[float] = []
        self.return_history: list[float] = []
        self.last_action: float = 0.0
        self.last_reward: float = 0.0
        self._rng = random.Random(seed)

    @abstractmethod
    def decide(self, market_state: MarketState | Mapping[str, Any]) -> float:
        """Return action intensity in [-max_risk, max_risk]."""
        raise NotImplementedError

    def update(self, returns: float) -> None:
        """Update resources from environment return/reward.

        The legacy behavior is preserved: capital *= (1 + returns).
        """
        safe_return = self._safe_float(returns, float("nan"))
        if not math.isfinite(safe_return):
            raise ValueError("returns must be finite")

        self.last_reward = safe_return
        self.capital = max(0.0, self.capital * (1.0 + safe_return))
        self.history.append(self.capital)
        self.return_history.append(safe_return)

    def act_and_update(self, market_state: MarketState | Mapping[str, Any], environment_return: float) -> float:
        """Decide exposure, apply exposed return, and return action."""
        action = self.decide(market_state)
        action = max(-self.max_risk, min(self.max_risk, self._safe_float(action, 0.0)))
        self.last_action = action
        self.action_history.append(action)

        exposed_return = action * self._safe_float(environment_return, 0.0)
        self.update(exposed_return)
        return action

    def reset(self) -> None:
        """Reset agent to initial capital and clear histories."""
        self.capital = self.initial_capital
        self.history = [self.capital]
        self.action_history = []
        self.return_history = []
        self.last_action = 0.0
        self.last_reward = 0.0

    def total_return(self) -> float:
        """Return cumulative return relative to initial capital."""
        return (self.capital / self.initial_capital) - 1.0

    def snapshot(self) -> AgentSnapshot:
        """Return serializable agent metrics."""
        returns = list(self.return_history)
        mean_return = statistics.fmean(returns) if returns else 0.0
        volatility = statistics.pstdev(returns) if len(returns) > 1 else 0.0

        return AgentSnapshot(
            capital=self.capital,
            initial_capital=self.initial_capital,
            max_risk=self.max_risk,
            total_return=self.total_return(),
            steps=max(0, len(self.history) - 1),
            last_action=self.last_action,
            last_reward=self.last_reward,
            mean_return=mean_return,
            volatility=volatility,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly agent state."""
        snapshot = self.snapshot()
        return {
            "capital": snapshot.capital,
            "initial_capital": snapshot.initial_capital,
            "max_risk": snapshot.max_risk,
            "total_return": snapshot.total_return,
            "steps": snapshot.steps,
            "last_action": snapshot.last_action,
            "last_reward": snapshot.last_reward,
            "mean_return": snapshot.mean_return,
            "volatility": snapshot.volatility,
            "history": list(self.history),
            "action_history": list(self.action_history),
            "return_history": list(self.return_history),
        }

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default


class KellyAgent(BaseAgent):
    """Resource allocation agent using fractional Kelly-style sizing."""

    __slots__ = ("phi", "p_success")

    def __init__(
        self,
        capital: float,
        max_risk: float = 0.02,
        phi: float = 0.25,
        *,
        p_success: float = 0.5,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(capital, max_risk, seed=seed)

        if not math.isfinite(float(phi)) or float(phi) < 0:
            raise ValueError("phi must be a non-negative finite number")

        self.phi: Final[float] = float(phi)
        self.p_success: Final[float] = max(0.0, min(1.0, float(p_success)))

    def decide(self, market_state: MarketState | Mapping[str, Any]) -> float:
        """Decide action intensity using a fractional Kelly-style estimate."""
        vol = self._safe_float(
            market_state.get("volatility_estimate", market_state.get("risk", 0.0)),
            0.0,
        )

        safe_vol = max(vol, 0.0001)
        reward_estimate = abs(self._safe_float(market_state.get("reward_estimate", 0.01), 0.01))
        odds = max(1e-9, reward_estimate / safe_vol)

        kelly_fraction = self.p_success - ((1.0 - self.p_success) / odds)
        scaled_fraction = kelly_fraction * self.phi

        return max(-self.max_risk, min(self.max_risk, scaled_fraction))


class RandomAgent(BaseAgent):
    """Baseline stochastic agent."""

    __slots__ = ()

    def decide(self, market_state: MarketState | Mapping[str, Any]) -> float:
        """Return random action intensity."""
        del market_state
        return self._rng.uniform(-self.max_risk, self.max_risk)


class CautiousAgent(BaseAgent):
    """Simple conservative baseline that reduces exposure as risk rises."""

    __slots__ = ()

    def decide(self, market_state: MarketState | Mapping[str, Any]) -> float:
        risk = self._safe_float(
            market_state.get("volatility_estimate", market_state.get("risk", 0.0)),
            0.0,
        )
        surprise = self._safe_float(market_state.get("surprise", 0.0), 0.0)
        risk_pressure = max(0.0, min(1.0, risk * 10.0 + surprise))
        return self.max_risk * max(0.0, 1.0 - risk_pressure)


class MomentumAgent(BaseAgent):
    """Baseline agent using latest price/value momentum when available."""

    __slots__ = ("_last_value",)

    def __init__(self, capital: float, max_risk: float = 0.02, *, seed: Optional[int] = None) -> None:
        super().__init__(capital, max_risk, seed=seed)
        self._last_value: Optional[float] = None

    def decide(self, market_state: MarketState | Mapping[str, Any]) -> float:
        value = self._safe_float(market_state.get("price", market_state.get("value", 0.0)), 0.0)

        if value <= 0:
            return 0.0

        if self._last_value is None:
            self._last_value = value
            return 0.0

        momentum = (value - self._last_value) / max(abs(self._last_value), 1e-9)
        self._last_value = value

        if momentum > 0:
            return min(self.max_risk, abs(momentum))
        if momentum < 0:
            return -min(self.max_risk, abs(momentum))
        return 0.0