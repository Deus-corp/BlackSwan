"""
This module defines various agent types for financial simulations.

Agents decide on investment proportions based on their strategies and
update their capital based on market returns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict, Final, List
import numpy as np


class MarketState(TypedDict):
    """
    A dictionary representing the current state of the market.

    Attributes:
        volatility_estimate (float): The estimated volatility of the market.
    """
    volatility_estimate: float


class BaseAgent(ABC):
    """
    Abstract base class for a financial agent.

    An agent has initial capital, current capital, a maximum risk appetite,
    and maintains a history of its capital over time.
    """
    __slots__ = ('initial_capital', 'capital', 'max_risk', 'history')

    def __init__(self, capital: float, max_risk: float = 0.02) -> None:
        """
        Initializes the BaseAgent.

        Args:
            capital: The initial capital. Must be positive.
            max_risk: The maximum proportion of capital to risk. Must be in [0, 1].

        Raises:
            ValueError: If inputs are invalid.
        """
        if not isinstance(capital, (int, float)) or capital <= 0:
            raise ValueError("Capital must be a positive number.")
        if not (0 <= max_risk <= 1):
            raise ValueError("Max risk must be a number between 0 and 1.")

        self.initial_capital: Final[float] = float(capital)
        self.capital: float = float(capital)
        self.max_risk: Final[float] = float(max_risk)
        self.history: List[float] = [self.capital]

    @abstractmethod
    def decide(self, market_state: MarketState) -> float:
        """
        Decides the proportion of capital to invest.

        Returns:
            float: The proportion to invest (long > 0, short < 0).
        """
        raise NotImplementedError

    def update(self, returns: float) -> None:
        """
        Updates the agent's capital based on market returns.

        Args:
            returns: The market return for the current period.

        Raises:
            ValueError: If `returns` is not finite.
        """
        if not np.isfinite(returns):
            raise ValueError("Returns must be finite.")
        self.capital *= (1.0 + returns)
        self.history.append(self.capital)


class KellyAgent(BaseAgent):
    """
    An agent that uses a modified Kelly criterion for position sizing.
    """
    __slots__ = ('phi', 'p_success')

    def __init__(self, capital: float, max_risk: float = 0.02, phi: float = 0.25) -> None:
        """
        Initializes the KellyAgent.

        Args:
            capital: Initial capital.
            max_risk: Maximum allowed risk.
            phi: The 'caution' coefficient (fractional Kelly scale).
        """
        super().__init__(capital, max_risk)
        if phi < 0:
            raise ValueError("Phi must be a non-negative number.")
        self.phi: Final[float] = float(phi)
        self.p_success: Final[float] = 0.5

    def decide(self, market_state: MarketState) -> float:
        """
        Decides investment using a fractional Kelly criterion.

        Args:
            market_state: Dict containing 'volatility_estimate'.
        """
        vol: float = market_state.get('volatility_estimate', 0.0)
        if vol <= 0:
            raise ValueError("Volatility estimate must be a positive number.")
            
        # Clamp volatility to prevent extreme positions
        safe_vol = max(vol, 0.0001)
        odds: float = 0.01 / safe_vol
        kelly_fraction: float = self.p_success - (1.0 - self.p_success) / odds * self.phi
        
        return float(np.clip(kelly_fraction, -self.max_risk, self.max_risk))


class RandomAgent(BaseAgent):
    """
    A simple agent that makes random investment decisions.
    """
    __slots__ = ()

    def decide(self, market_state: MarketState) -> float:
        """
        Decides a random proportion of capital to invest.
        """
        return float(np.random.uniform(-self.max_risk, self.max_risk))