"""Metrics utilities for BlackSwan simulation experiments.

The module keeps the legacy `compute_metrics(history)` API while broadening the
terminology from trading-only capital curves to generic resource/value curves.

It can be used for:
- trade capital histories,
- agent resource histories,
- environment value trajectories,
- simulation reward curves,
- swarm viability scores.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Optional

import matplotlib.pyplot as plt
import numpy as np


METRICS_KEYS: Final[list[str]] = [
    "final_capital",
    "sharpe_ratio",
    "max_drawdown",
    "mean_return",
    "volatility",
]

EXTENDED_METRICS_KEYS: Final[list[str]] = [
    *METRICS_KEYS,
    "initial_value",
    "final_value",
    "total_return",
    "min_value",
    "max_value",
    "steps",
    "positive_return_rate",
    "calmar_ratio",
]


def compute_metrics(history: Sequence[float], risk_free_rate: float = 0.0) -> dict[str, float]:
    """Compute legacy performance metrics from a positive value/resource history."""
    extended = compute_extended_metrics(history, risk_free_rate=risk_free_rate)
    return {key: float(extended[key]) for key in METRICS_KEYS}


def compute_extended_metrics(history: Sequence[float], risk_free_rate: float = 0.0) -> dict[str, float]:
    """Compute extended metrics for a generic positive resource/value trajectory."""
    history_arr = _validate_history(history)
    risk_free = _safe_finite(risk_free_rate, "risk_free_rate")

    returns = np.diff(history_arr) / history_arr[:-1]
    if not np.all(np.isfinite(returns)):
        raise ValueError("computed returns contain non-finite values")

    excess_returns = returns - risk_free
    std_excess = float(np.std(excess_returns))
    sharpe_ratio = float(np.mean(excess_returns) / std_excess) if std_excess > 0 else 0.0

    peak = np.maximum.accumulate(history_arr)
    drawdown = (history_arr - peak) / peak
    max_drawdown = float(np.min(drawdown))

    total_return = float((history_arr[-1] / history_arr[0]) - 1.0)
    positive_return_rate = float(np.mean(returns > 0.0)) if returns.size else 0.0
    calmar_ratio = float(total_return / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    final_value = float(history_arr[-1])

    return {
        # Legacy names.
        "final_capital": final_value,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "mean_return": float(np.mean(returns)) if returns.size else 0.0,
        "volatility": float(np.std(returns)) if returns.size else 0.0,
        # Generic names.
        "initial_value": float(history_arr[0]),
        "final_value": final_value,
        "total_return": total_return,
        "min_value": float(np.min(history_arr)),
        "max_value": float(np.max(history_arr)),
        "steps": float(max(0, len(history_arr) - 1)),
        "positive_return_rate": positive_return_rate,
        "calmar_ratio": calmar_ratio,
    }


def compute_agents_metrics(
    agents_data: Mapping[str, tuple[Sequence[float], Any] | Sequence[float]],
    *,
    risk_free_rate: float = 0.0,
) -> dict[str, dict[str, float]]:
    """Compute metrics for many agents/resources."""
    results: dict[str, dict[str, float]] = {}

    for name, value in agents_data.items():
        if isinstance(value, tuple) and value:
            history = value[0]
        else:
            history = value

        results[str(name)] = compute_extended_metrics(history, risk_free_rate=risk_free_rate)

    return results


def summarize_metrics(metrics: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """Aggregate per-agent metrics into a compact summary."""
    if not metrics:
        return {
            "agent_count": 0.0,
            "best_final_value": 0.0,
            "mean_final_value": 0.0,
            "best_sharpe_ratio": 0.0,
            "worst_drawdown": 0.0,
        }

    final_values = [float(item.get("final_value", item.get("final_capital", 0.0))) for item in metrics.values()]
    sharpe_values = [float(item.get("sharpe_ratio", 0.0)) for item in metrics.values()]
    drawdowns = [float(item.get("max_drawdown", 0.0)) for item in metrics.values()]

    return {
        "agent_count": float(len(metrics)),
        "best_final_value": max(final_values),
        "mean_final_value": float(np.mean(final_values)),
        "best_sharpe_ratio": max(sharpe_values),
        "worst_drawdown": min(drawdowns),
    }


def plot_results(
    agents_data: Mapping[str, tuple[Sequence[float], Any] | Sequence[float]],
    title: str = "Simulation Results",
    *,
    output_file: Optional[str | Path] = None,
    show: bool = True,
) -> Optional[Path]:
    """Visualize agent/resource histories and optional environment trajectory.

    Returns the saved output path when output_file is provided.
    """
    if not agents_data:
        raise ValueError("agents_data cannot be empty")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle(title, fontsize=16)

    sample_agent: Any = None

    for name, value in agents_data.items():
        if isinstance(value, tuple):
            history = value[0]
            if sample_agent is None and len(value) > 1:
                sample_agent = value[1]
        else:
            history = value

        history_arr = np.asarray(history, dtype=np.float64)
        if history_arr.size == 0:
            continue

        ax1.plot(history_arr, label=str(name))

    ax1.set(title="Agent Resources Over Time", xlabel="Step", ylabel="Resources / Capital")
    ax1.legend()
    ax1.grid(True)

    market = getattr(sample_agent, "market", None)
    prices = getattr(market, "prices", None) or getattr(market, "values", None)

    if prices is not None:
        ax2.plot(np.asarray(prices, dtype=np.float64), label="Environment Value")
        ax2.set(title="Environment Value Over Time", xlabel="Step", ylabel="Value")
        ax2.grid(True)
        ax2.legend()
    else:
        ax2.set_visible(False)

    plt.tight_layout(rect=(0, 0.03, 1, 0.95))

    saved_path: Optional[Path] = None
    if output_file:
        saved_path = Path(output_file)
        saved_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(saved_path, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return saved_path


def _validate_history(history: Sequence[float]) -> np.ndarray:
    if len(history) < 2:
        raise ValueError("history must contain at least two elements")

    history_arr = np.asarray(history, dtype=np.float64)

    if not np.all(np.isfinite(history_arr)):
        raise ValueError("history must contain only finite values")

    if np.any(history_arr <= 0):
        raise ValueError("history must contain only positive non-zero values")

    return history_arr


def _safe_finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc

    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")

    return number