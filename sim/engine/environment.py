"""
A market model simulating asset price evolution using Geometric Brownian Motion (GBM).

The price movement follows the stochastic differential equation: dS/S = μ*dt + σ*dW,
where drift (μ) and volatility (σ) are configurable parameters.
"""

from __future__ import annotations

from typing import Final, TypedDict, List
import numpy as np


class MarketState(TypedDict):
    """Typed dictionary for market state representation."""
    price: float
    volatility_estimate: float


class MarketEnvironment:
    """
    Simulates asset price evolution using a Geometric Brownian Motion (GBM) model.

    Attributes:
        volatility: The standard deviation of returns per step (sigma).
        drift: The long-term average return per step (mu).
        lookback_period: Number of periods used to calculate realized volatility.
        prices: Historical record of asset prices.
    """

    __slots__ = ("volatility", "drift", "lookback_period", "prices")

    def __init__(self, volatility: float = 0.02, drift: float = 0.0, lookback_period: int = 100) -> None:
        """
        Initializes the simulation environment.

        Args:
            volatility: Non-negative standard deviation (sigma).
            drift: Expected return (mu).
            lookback_period: Positive integer for historical window.

        Raises:
            ValueError: If parameters violate mathematical or logic constraints.
        """
        if volatility < 0:
            raise ValueError("Volatility must be a non-negative float.")
        if lookback_period <= 0:
            raise ValueError("Lookback period must be a positive integer.")

        self.volatility: Final[float] = float(volatility)
        self.drift: Final[float] = float(drift)
        self.lookback_period: Final[int] = lookback_period
        self.prices: List[float] = [1.0]

    def step(self) -> float:
        """
        Advances the simulation by one time step.

        Returns:
            The new asset price after applying the GBM step.

        Raises:
            ValueError: If the resulting price is non-finite or non-positive.
        """
        last_price: float = self.prices[-1]
        returns: float = float(np.random.normal(loc=self.drift, scale=self.volatility))
        new_price: float = last_price * (1.0 + returns)

        if not np.isfinite(new_price) or new_price <= 0:
            raise ValueError(f"Simulation error: invalid price generated: {new_price}")

        self.prices.append(new_price)
        return new_price

    def get_state(self) -> MarketState:
        """
        Retrieves current market metrics.

        Returns:
            MarketState containing current price and estimated realized volatility.
        """
        current_price: float = self.prices[-1]

        if len(self.prices) < 2:
            vol_estimate: float = self.volatility
        else:
            # Calculate realized volatility over the lookback window
            start_idx: int = max(0, len(self.prices) - (self.lookback_period + 1))
            window: np.ndarray = np.array(self.prices[start_idx:])
            returns: np.ndarray = np.diff(window) / window[:-1]

            vol_estimate = float(np.std(returns)) if returns.size > 0 else self.volatility

        return {
            "price": current_price,
            "volatility_estimate": vol_estimate
        }