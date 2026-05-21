from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Any, Optional, Final

METRICS_KEYS: Final[List[str]] = [
    "final_capital", "sharpe_ratio", "max_drawdown", "mean_return", "volatility"
]


def compute_metrics(history: List[float], risk_free_rate: float = 0.0) -> Dict[str, float]:
    """
    Computes key performance metrics for an investment history.

    Metrics include Sharpe Ratio, Maximum Drawdown, Final Capital, Mean Return,
    and Volatility of Returns.

    Args:
        history: A list of capital (or asset price) values over time.
                 Must contain at least two positive, non-zero values to compute returns.
        risk_free_rate: The per-period risk-free rate, used for Sharpe Ratio calculation.
                        Assumed to be consistent with the frequency of `history` steps.

    Returns:
        A dictionary containing the computed metrics:
        - "final_capital": The last value in the history list.
        - "sharpe_ratio": The per-period Sharpe Ratio.
        - "max_drawdown": The maximum percentage drop from a peak value.
        - "mean_return": The average per-period return.
        - "volatility": The standard deviation of per-period returns.

    Raises:
        ValueError: If `history` has fewer than two elements, contains non-positive values,
                   or if `risk_free_rate` is not finite.
    """
    if len(history) < 2:
        raise ValueError("History must contain at least two elements to compute metrics.")
    
    if not np.isfinite(risk_free_rate):
        raise ValueError("Risk-free rate must be a finite value.")
    
    history_arr: np.ndarray = np.array(history, dtype=np.float64)
    
    if np.any(history_arr <= 0):
        raise ValueError("History must contain only positive, non-zero values.")
    
    # Calculate periodic returns
    returns: np.ndarray = np.diff(history_arr) / history_arr[:-1]
    
    if not np.all(np.isfinite(returns)):
        raise ValueError("Computed returns contain non-finite values.")

    # Calculate excess returns for Sharpe Ratio
    excess_returns: np.ndarray = returns - risk_free_rate

    # Sharpe Ratio: (Mean Excess Return) / (Std Dev of Excess Returns)
    std_excess_returns: float = np.std(excess_returns)
    sharpe_ratio: float = np.mean(excess_returns) / std_excess_returns if std_excess_returns > 0 else 0.0

    # Maximum Drawdown calculation
    peak: np.ndarray = np.maximum.accumulate(history_arr)
    drawdown: np.ndarray = (history_arr - peak) / peak
    max_drawdown: float = np.min(drawdown)

    return {
        "final_capital": float(history_arr[-1]),
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "mean_return": float(np.mean(returns)),
        "volatility": float(np.std(returns))
    }


def plot_results(agents_data: Dict[str, Tuple[List[float], Any]], title: str = "Simulation Results") -> None:
    """
    Plots the capital history of agents and the market price over time.

    Assumes all agents in `agents_data` are part of the same market environment,
    and that `agent` objects have a 'market' attribute with a 'prices' list.

    Args:
        agents_data: A dictionary where keys are agent names (str) and values
                     are tuples. Each tuple contains:
                     - A list of floats representing the agent's capital history.
                     - The agent object itself (used to access market data).
        title: The overall title for the plot.

    Raises:
        ValueError: If `agents_data` is empty or if market price data is not accessible.
    """
    if not agents_data:
        raise ValueError("Agents data cannot be empty.")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle(title, fontsize=16)

    # Plot Agent Capital over time
    for name, (capital_history, _) in agents_data.items():
        ax1.plot(capital_history, label=name)
    ax1.set_title("Agent Capital Over Time")
    ax1.set_xlabel("Simulation Step")
    ax1.set_ylabel("Capital")
    ax1.legend()
    ax1.grid(True)

    # Plot Market Price over time
    try:
        sample_agent_data = next(iter(agents_data.values()))
        sample_agent = sample_agent_data[1]
        if hasattr(sample_agent, 'market') and hasattr(sample_agent.market, 'prices'):
            market_prices: List[float] = sample_agent.market.prices
            ax2.plot(market_prices, color='black', alpha=0.7, label="Market Price")
            ax2.set_title("Market Price Over Time")
            ax2.set_xlabel("Simulation Step")
            ax2.set_ylabel("Price")
            ax2.grid(True)
            ax2.legend()
        else:
            ax2.set_visible(False)
            raise ValueError("Market price data not found on agent.")
    except Exception as e:
        ax2.set_visible(False)
        raise ValueError(f"Error accessing market price data: {str(e)}")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()