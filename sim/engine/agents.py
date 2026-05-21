"""
This module defines various agent types for financial simulations.

Agents decide on investment proportions based on their strategies and
update their capital based on market returns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Final, TypedDict
import numpy as np


class MarketState(TypedDict):
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
            capital: The initial capital of the agent. Must be positive.
            max_risk: The maximum proportion of capital the agent is
                      willing to risk on a single trade. Must be in [0, 1].

        Raises:
            ValueError: If `capital` is not positive or `max_risk` is not in [0, 1].
        """
        if not isinstance(capital, (int, float)) or capital <= 0:
            raise ValueError("Capital must be a positive number.")
        if not isinstance(max_risk, (int, float)) or max_risk < 0 or max_risk > 1:
            raise ValueError("Max risk must be a number between 0 and 1.")

        self.initial_capital: Final[float] = capital
        self.capital: float = capital
        self.max_risk: Final[float] = max_risk
        self.history: List[float] = [capital]

    @abstractmethod
    def decide(self, market_state: Dict[str, Any]) -> float:
        """
        Decides the proportion of capital to invest.

        A positive return value indicates a long position (buy),
        while a negative value indicates a short position (sell).
        The magnitude of the value must be within [-self.max_risk, self.max_risk].

        Args:
            market_state: A dictionary containing current market information,
                          e.g., {"volatility_estimate": 0.02}.

        Returns:
            The proportion of capital to invest (e.g., 0.01 for 1% long,
            -0.01 for 1% short).

        Raises:
            ValueError: If `market_state` is invalid or missing required keys.
        """
        raise NotImplementedError

    def update(self, returns: float) -> None:
        """
        Updates the agent's capital based on market returns.

        Args:
            returns: The market return for the current period (e.g., 0.01 for 1% gain).
                     Must be finite.

        Raises:
            ValueError: If `returns` is not finite.
        """
        if not np.isfinite(returns):
            raise ValueError("Returns must be finite.")
        self.capital *= (1 + returns)
        self.history.append(self.capital)


class KellyAgent(BaseAgent):
    """
    An agent that uses a modified Kelly criterion for position sizing.

    This implementation uses simplified heuristics for estimating probabilities
    and odds, and a fractional Kelly approach. The 'phi' coefficient is applied
    to the 'loss' component of the formula, which is a specific modification.
    """
    __slots__ = ('phi', 'p_success')

    def __init__(self, capital: float, max_risk: float = 0.02, phi: float = 0.25) -> None:
        """
        Initializes the KellyAgent.

        Args:
            capital: The initial capital of the agent. Must be positive.
            max_risk: The maximum proportion of capital the agent is
                      willing to risk on a single trade. Must be in [0, 1].
            phi: The 'caution' coefficient for the Kelly criterion (fractional Kelly).
                 Must be non-negative. A value of 1.0 is full Kelly, less than 1.0 is fractional.
                 In this implementation, phi scales the 'loss' component of the formula.

        Raises:
            ValueError: If `capital` is not positive, `max_risk` is not in [0, 1], or `phi` is negative.
        """
        super().__init__(capital, max_risk)
        if not isinstance(phi, (int, float)) or phi < 0:
            raise ValueError("Phi must be a non-negative number.")
        self.phi: Final[float] = phi
        self.p_success: Final[float] = 0.5

    def decide(self, market_state: Dict[str, Any]) -> float:
        """
        Decides the proportion of capital to invest using a modified Kelly criterion.

        Uses market volatility as a proxy for risk/odds.
        The agent can take both long and short positions, limited by `max_risk`.

        Args:
            market_state: A dictionary containing market information, expected to
                          include "volatility_estimate".

        Returns:
            The proportion of capital to invest, clipped between -max_risk and +max_risk.

        Raises:
            ValueError: If `market_state` is invalid or "volatility_estimate" is non-positive.
        """
        if not isinstance(market_state, dict) or 'volatility_estimate' not in market_state:
            raise ValueError("Market state must be a dictionary containing 'volatility_estimate'.")

        vol: float = market_state['volatility_estimate']
        if not isinstance(vol, (int, float)) or vol <= 0:
            raise ValueError("Volatility estimate must be a positive number.")
        vol = max(vol, 0.0001)

        odds: float = 0.01 / vol
        kelly_fraction: float = self.p_success - (1 - self.p_success) / odds * self.phi
        return np.clip(kelly_fraction, -self.max_risk, self.max_risk)


class RandomAgent(BaseAgent):
    """
    A simple agent that makes random investment decisions.

    This agent randomly decides to go long or short within its allowed
    maximum risk appetite.
    """
    __slots__ = ()

    def decide(self, market_state: Dict[str, Any]) -> float:
        """
        Decides a random proportion of capital to invest.

        The decision is uniformly random between -self.max_risk and +self.max_risk.

        Args:
            market_state: A dictionary containing current market information (not used by this agent).

        Returns:
            A random proportion of capital to invest.
        """
        return np.random.uniform(-self.max_risk, self.max_risk)