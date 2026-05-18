import numpy as np
from typing import List, Dict

class MarketEnvironment:
    """
    A simple market model simulating asset price evolution using Geometric Brownian Motion (GBM).

    The price movement follows the formula: dS/S = μ*dt + σ*dW, where dt=1 for each step.
    """

    def __init__(self, volatility: float = 0.02, drift: float = 0.0):
        """
        Initializes the MarketEnvironment with specified volatility and drift.

        Args:
            volatility: The standard deviation of returns per step (sigma in GBM).
                        Represents the randomness or "jumpiness" of the price.
            drift: The long-term average return per step (mu in GBM).
                   A value of 0 results in a pure random walk.
        """
        if not isinstance(volatility, (int, float)) or volatility < 0:
            raise ValueError("Volatility must be a non-negative float.")
        if not isinstance(drift, (int, float)):
            raise ValueError("Drift must be a float.")

        self.volatility: float = volatility
        self.drift: float = drift
        self.prices: List[float] = [1.0]  # Initial price of the asset

    def step(self) -> float:
        """
        Advances the market simulation by one step.

        Calculates a new price based on the Geometric Brownian Motion model
        and appends it to the price history.

        Returns:
            The newly calculated price of the asset.
        """
        last_price = self.prices[-1]
        # Calculate returns using a normal distribution
        # dS/S = μ*dt + σ*dW, with dt=1 for each step
        returns = np.random.normal(loc=self.drift, scale=self.volatility)
        new_price = last_price * (1 + returns)
        self.prices.append(new_price)
        return new_price

    def get_state(self) -> Dict[str, float]:
        """
        Returns the current state of the market.

        This includes the current asset price and an estimate of recent
        market volatility based on the standard deviation of returns.

        Returns:
            A dictionary containing:
            - "price": The most recent asset price.
            - "volatility_estimate": The estimated standard deviation of returns
                                     over the last 100 periods, or the initial
                                     volatility if not enough data is available.
        """
        current_price = self.prices[-1]
        
        # To estimate volatility of returns over the last N steps,
        # we need N+1 price points.
        lookback_period = 100
        volatility_estimate: float
        
        if len(self.prices) > lookback_period: 
            # We have enough data for `lookback_period` returns
            # Get prices for the last `lookback_period` returns (i.e., `lookback_period` + 1 prices)
            recent_prices_arr = np.array(self.prices[-(lookback_period + 1):])
            recent_returns = np.diff(recent_prices_arr) / recent_prices_arr[:-1]
            volatility_estimate = np.std(recent_returns)
        elif len(self.prices) >= 2: 
            # If less than `lookback_period` but at least 2 prices,
            # calculate volatility based on all available returns.
            all_prices_arr = np.array(self.prices)
            all_returns = np.diff(all_prices_arr) / all_prices_arr[:-1]
            volatility_estimate = np.std(all_returns) if len(all_returns) > 0 else self.volatility
        else:
            # If only one price point or less, cannot calculate returns volatility.
            # Fall back to the initial configured volatility.
            volatility_estimate = self.volatility
            
        return {
            "price": current_price,
            "volatility_estimate": volatility_estimate
        }