from __future__ import annotations

from typing import Any, Dict, Final, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

METRICS_KEYS: Final[List[str]] = [
    "final_capital",
    "sharpe_ratio",
    "max_drawdown",
    "mean_return",
    "volatility",
]


def compute_metrics(history: List[float], risk_free_rate: float = 0.0) -> Dict[str, float]:
    """
    Computes performance metrics based on capital history.

    Args:
        history: Sequence of capital values. Must contain at least two positive values.
        risk_free_rate: Per-period risk-free rate.

    Returns:
        Dictionary of calculated financial performance metrics.

    Raises:
        ValueError: If input data is insufficient, non-positive, or non-finite.
    """
    if len(history) < 2:
        raise ValueError("History must contain at least two elements.")
    if not np.isfinite(risk_free_rate):
        raise ValueError("Risk-free rate must be a finite value.")

    history_arr = np.array(history, dtype=np.float64)
    if np.any(history_arr <= 0):
        raise ValueError("History must contain only positive, non-zero values.")

    returns = np.diff(history_arr) / history_arr[:-1]
    if not np.all(np.isfinite(returns)):
        raise ValueError("Computed returns contain non-finite values.")

    excess_returns = returns - risk_free_rate
    std_excess = np.std(excess_returns)
    sharpe_ratio = float(np.mean(excess_returns) / std_excess) if std_excess > 0 else 0.0

    peak = np.maximum.accumulate(history_arr)
    drawdown = (history_arr - peak) / peak
    max_drawdown = float(np.min(drawdown))

    return {
        "final_capital": float(history_arr[-1]),
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "mean_return": float(np.mean(returns)),
        "volatility": float(np.std(returns)),
    }


def plot_results(
    agents_data: Dict[str, Tuple[List[float], Any]], title: str = "Simulation Results"
) -> None:
    """
    Visualizes agent capital and market trends.

    Args:
        agents_data: Dict mapping agent names to (capital_history, agent_instance).
        title: Plot title.
    """
    if not agents_data:
        raise ValueError("Agents data cannot be empty.")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle(title, fontsize=16)

    for name, (history, _) in agents_data.items():
        ax1.plot(history, label=name)
    ax1.set(title="Agent Capital Over Time", xlabel="Step", ylabel="Capital")
    ax1.legend()
    ax1.grid(True)

    sample_agent = next(iter(agents_data.values()))[1]
    market = getattr(sample_agent, "market", None)
    prices = getattr(market, "prices", None)

    if prices is not None:
        ax2.plot(prices, color="black", alpha=0.7, label="Market Price")
        ax2.set(title="Market Price Over Time", xlabel="Step", ylabel="Price")
        ax2.grid(True)
        ax2.legend()
    else:
        ax2.set_visible(False)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()