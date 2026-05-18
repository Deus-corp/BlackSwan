"""
This module defines various agent types for financial simulations.

Agents decide on investment proportions based on their strategies and
update their capital based on market returns.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import numpy as np


class BaseAgent(ABC):
    """
    Abstract base class for a financial agent.

    An agent has initial capital, current capital, a maximum risk appetite,
    and maintains a history of its capital over time.
    """

    def __init__(self, capital: float, max_risk: float = 0.02) -> None:
        """
        Initializes the BaseAgent.

        Args:
            capital: The initial capital of the agent.
            max_risk: The maximum proportion of capital the agent is
                      willing to risk on a single trade. This is an
                      absolute value, so a trade can range from
                      -max_risk (short) to +max_risk (long).
        """
        self.initial_capital: float = capital
        self.capital: float = capital
        self.max_risk: float = max_risk
        self.history: List[float] = [capital]  # History of capital

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
        """
        ...

    def update(self, returns: float) -> None:
        """
        Updates the agent's capital based on market returns.

        Args:
            returns: The market return for the current period (e.g., 0.01 for 1% gain).
        """
        self.capital *= (1 + returns)
        self.history.append(self.capital)


class KellyAgent(BaseAgent):
    """
    An agent that uses a modified Kelly criterion for position sizing.

    This implementation uses simplified heuristics for estimating probabilities
    and odds, and a fractional Kelly approach.
    """

    def __init__(self, capital: float, max_risk: float = 0.02, phi: float = 0.25) -> None:
        """
        Initializes the KellyAgent.

        Args:
            capital: The initial capital of the agent.
            max_risk: The maximum proportion of capital the agent is
                      willing to risk on a single trade.
            phi: The 'caution' coefficient for the Kelly criterion (fractional Kelly).
                 A value of 1.0 is full Kelly, less than 1.0 is fractional.
                 In this implementation, phi scales the 'loss' component of the formula.
        """
        super().__init__(capital, max_risk)
        self.phi: float = phi
        # Simplified: A fixed estimation for probability of success.
        # In a more advanced Kelly Agent, this would be dynamically estimated.
        self.p_success: float = 0.5

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
        """
        # Simplified: Use volatility as an indicator of risk.
        # Default to 0.02 if not provided to prevent division by zero or errors.
        vol: float = market_state.get("volatility_estimate", 0.02)
        if vol <= 0:  # Ensure volatility is positive for odds calculation
            vol = 0.0001 # Small positive value to avoid division by zero

        # Heuristic for odds (b ≈ return/risk). Here, 0.01 is a placeholder for
        # expected profit per unit of risk.
        odds: float = 0.01 / vol

        # Calculate Kelly fraction: f = p - (1-p)/b
        # The 'phi' coefficient is applied to the (1-p)/b term, which is a
        # specific modification rather than standard fractional Kelly (phi * f).
        kelly_fraction: float = self.p_success - (1 - self.p_success) / odds * self.phi

        # Limit the fraction to the allowed risk appetite, allowing for both
        # long (positive) and short (negative) positions.
        return np.clip(kelly_fraction, -self.max_risk, self.max_risk)


class RandomAgent(BaseAgent):
    """
    A simple agent that makes random investment decisions.

    This agent randomly decides to go long or short within its allowed
    maximum risk appetite.
    """

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