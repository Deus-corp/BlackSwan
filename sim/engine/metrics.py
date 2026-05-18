import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Any

def compute_metrics(history: List[float], risk_free_rate: float = 0.0) -> Dict[str, float]:
    """
    Computes key performance metrics for an investment history.

    Metrics include Sharpe Ratio, Maximum Drawdown, Final Capital, Mean Return,
    and Volatility of Returns.

    Args:
        history: A list of capital (or asset price) values over time.
                 Must contain at least two values to compute returns.
        risk_free_rate: The per-period risk-free rate, used for Sharpe Ratio calculation.
                        Assumed to be consistent with the frequency of `history` steps.

    Returns:
        A dictionary containing the computed metrics:
        - "final_capital": The last value in the history list.
        - "sharpe_ratio": The per-period Sharpe Ratio.
        - "max_drawdown": The maximum percentage drop from a peak value.
        - "mean_return": The average per-period return.
        - "volatility": The standard deviation of per-period returns.
        Returns an empty dictionary if `history` has fewer than two elements.
    """
    if len(history) < 2:
        return {}

    # Convert history to a NumPy array for efficient calculations
    history_arr = np.array(history)

    # Calculate periodic returns
    returns = np.diff(history_arr) / history_arr[:-1]

    # Calculate excess returns for Sharpe Ratio
    excess_returns = returns - risk_free_rate

    # Sharpe Ratio: (Mean Excess Return) / (Std Dev of Excess Returns)
    # Handle case where standard deviation is zero to prevent division by zero.
    std_excess_returns = np.std(excess_returns)
    sharpe_ratio = np.mean(excess_returns) / std_excess_returns if std_excess_returns > 0 else 0.0

    # Maximum Drawdown calculation
    # Accumulate maximum values up to each point
    peak = np.maximum.accumulate(history_arr)
    # Calculate drawdown from peak
    drawdown = (history_arr - peak) / peak
    # Max drawdown is the minimum (most negative) drawdown
    max_drawdown = np.min(drawdown)

    return {
        "final_capital": history_arr[-1],
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "mean_return": np.mean(returns),
        "volatility": np.std(returns)
    }

def plot_results(agents_data: Dict[str, Tuple[List[float], Any]], title: str = "Simulation Results"):
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
    """
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
    if agents_data:
        # Assuming all agents interact with the same market
        sample_agent = list(agents_data.values())[0][1]
        if hasattr(sample_agent, 'market') and hasattr(sample_agent.market, 'prices'):
            market_prices = sample_agent.market.prices
            ax2.plot(market_prices, color='black', alpha=0.7, label="Market Price")
            ax2.set_title("Market Price Over Time")
            ax2.set_xlabel("Simulation Step")
            ax2.set_ylabel("Price")
            ax2.grid(True)
        else:
            ax2.set_visible(False) # Hide the market price plot if data not available
            print("Warning: Market price data not found on agent. Market price plot skipped.")
    else:
        ax2.set_visible(False) # Hide the market price plot if no agent data
        print("Warning: No agent data provided. Market price plot skipped.")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to make space for suptitle
    plt.show()