import numpy as np
import matplotlib.pyplot as plt
from typing import List

def compute_metrics(history: List[float], risk_free_rate: float = 0.0) -> dict:
    """Вычисляет ключевые метрики: Sharpe, max drawdown, итоговый капитал."""
    if len(history) < 2:
        return {}
    returns = np.diff(history) / history[:-1]
    excess = returns - risk_free_rate
    sharpe = np.mean(excess) / np.std(excess) if np.std(excess) > 0 else 0.0
    # Максимальная просадка
    peak = np.maximum.accumulate(history)
    drawdown = (history - peak) / peak
    max_drawdown = np.min(drawdown)
    return {
        "final_capital": history[-1],
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "mean_return": np.mean(returns),
        "volatility": np.std(returns)
    }

def plot_results(agents_data: dict, title="Simulation Results"):
    """Строит график капитала агентов и цену рынка."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    # Капитал
    for name, (history, agent) in agents_data.items():
        ax1.plot(history, label=name)
    ax1.set_title("Capital over time")
    ax1.set_xlabel("Step")
    ax1.set_ylabel("Capital")
    ax1.legend()
    ax1.grid(True)
    # Цена рынка
    if agents_data:
        sample_agent = list(agents_data.values())[0][1]
        if hasattr(sample_agent, 'market'):
            prices = sample_agent.market.prices
            ax2.plot(prices, color='black', alpha=0.7)
            ax2.set_title("Market price")
            ax2.set_xlabel("Step")
            ax2.set_ylabel("Price")
            ax2.grid(True)
    plt.tight_layout()
    plt.show()