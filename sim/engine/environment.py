"""
A simple market model simulating asset price evolution using Geometric Brownian Motion (GBM).

The price movement follows the formula: dS/S = μ*dt + σ*dW, where dt=1 for each step.
"""

from __future__ import annotations

from typing import List, Dict, Final
import numpy as np


class MarketEnvironment:
    """
    A simple market model simulating asset price evolution using Geometric Brownian Motion (GBM).

    The price movement follows the formula: dS/S = μ*dt + σ*dW, where dt=1 for each step.
    """
    __slots__ = ('volatility', 'drift', 'lookback_period', 'prices')

    def __init__(self, volatility: float = 0.02, drift: float = 0.0, lookback_period: int = 100) -> None:
        """
        Initializes the MarketEnvironment with specified volatility, drift, and lookback period.

        Args:
            volatility: The standard deviation of returns per step (sigma in GBM).
                        Represents the randomness or "jumpiness" of the price. Must be non-negative.
            drift: The long-term average return per step (mu in GBM).
                   A value of 0 results in a pure random walk.
            lookback_period: The number of recent returns to consider when estimating market volatility.
                             Must be a positive integer.

        Raises:
            ValueError: If `volatility` is negative, `drift` is not a number, or `lookback_period` is not a positive integer.
        """
        if not isinstance(volatility, (int, float)) or volatility < 0:
            raise ValueError("Volatility must be a non-negative float.")
        if not isinstance(drift, (int, float)):
            raise ValueError("Drift must be a float.")
        if not isinstance(lookback_period, int) or lookback_period <= 0:
            raise ValueError("Lookback period must be a positive integer.")

        self.volatility: Final[float] = volatility
        self.drift: Final[float] = drift
        self.lookback_period: Final[int] = lookback_period
        self.prices: List[float] = [1.0]

    def step(self) -> float:
        """
        Advances the market simulation by one step.

        Calculates a new price based on the Geometric Brownian Motion model
        and appends it to the price history.

        Returns:
            The newly calculated price of the asset.

        Raises:
            ValueError: If the new price is not finite or positive.
        """
        last_price: float = self.prices[-1]
        returns: float = np.random.normal(loc=self.drift, scale=self.volatility)
        new_price: float = last_price * (1 + returns)
        if not np.isfinite(new_price) or new_price <= 0:
            raise ValueError("New price must be finite and positive.")
        self.prices.append(new_price)
        return new_price

    def get_state(self) -> Dict[str, float]:
        """
        Returns the current state of the market.

        This includes the current asset price and an estimate of recent
        market volatility based on the standard deviation of returns
        over the configured `lookback_period`.

        Returns:
            A dictionary containing:
            - "price": The most recent asset price.
            - "volatility_estimate": The estimated standard deviation of returns
                                     over the last `lookback_period` periods,
                                     or all available periods if less than `lookback_period`,
                                     or the initial `volatility` if insufficient data.
        """
        current_price: float = self.prices[-1]
        volatility_estimate: float

        if len(self.prices) < 2:
            volatility_estimate = self.volatility
        else:
            start_index: int = max(0, len(self.prices) - (self.lookback_period + 1))
            recent_prices_arr: np.ndarray = np.array(self.prices[start_index:])
            returns: np.ndarray = np.diff(recent_prices_arr) / recent_prices_arr[:-1]

            if returns.size > 0:
                volatility_estimate = np.std(returns)
            else:
                volatility_estimate = self.volatility

        return {
            "price": current_price,
            "volatility_estimate": volatility_estimate
        }