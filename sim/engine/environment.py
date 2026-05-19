import numpy as np
from typing import List, Dict


class MarketEnvironment:
    """
    A simple market model simulating asset price evolution using Geometric Brownian Motion (GBM).

    The price movement follows the formula: dS/S = μ*dt + σ*dW, where dt=1 for each step.
    """

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
        """
        if not isinstance(volatility, (int, float)) or volatility < 0:
            raise ValueError("Volatility must be a non-negative float.")
        if not isinstance(drift, (int, float)):
            raise ValueError("Drift must be a float.")
        if not isinstance(lookback_period, int) or lookback_period <= 0:
            raise ValueError("Lookback period must be a positive integer.")

        self.volatility: float = volatility
        self.drift: float = drift
        self.lookback_period: int = lookback_period
        self.prices: List[float] = [1.0]  # Initial price of the asset

    def step(self) -> float:
        """
        Advances the market simulation by one step.

        Calculates a new price based on the Geometric Brownian Motion model
        and appends it to the price history.

        Returns:
            The newly calculated price of the asset.
        """
        last_price: float = self.prices[-1]
        # Calculate returns using a normal distribution
        # dS/S = μ*dt + σ*dW, with dt=1 for each step
        returns: float = np.random.normal(loc=self.drift, scale=self.volatility)
        new_price: float = last_price * (1 + returns)
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

        # Need at least 2 prices to calculate a return
        if len(self.prices) < 2:
            volatility_estimate = self.volatility
        else:
            # Determine the start index for slicing prices.
            # We need `lookback_period` returns, which requires `lookback_period + 1` price points.
            # `max(0, ...)` ensures we don't go beyond the actual start of the list.
            start_index: int = max(0, len(self.prices) - (self.lookback_period + 1))

            # Slice the prices array to get the relevant history
            recent_prices_arr: np.ndarray = np.array(self.prices[start_index:])

            # Calculate periodic returns from the sliced prices
            # np.diff requires at least 2 elements. We've ensured len(self.prices) >= 2 above.
            # If recent_prices_arr has only one element, np.diff will return an empty array.
            returns: np.ndarray = np.diff(recent_prices_arr) / recent_prices_arr[:-1]

            if returns.size > 0:
                volatility_estimate = np.std(returns)
            else:
                # This case should ideally not be reached if len(self.prices) >= 2,
                # but serves as a robust fallback.
                volatility_estimate = self.volatility

        return {
            "price": current_price,
            "volatility_estimate": volatility_estimate
        }