#!/usr/bin/env python3
"""CLI runner for BlackSwan simulation scenarios.

This is an experiment runner, not core swarm runtime. It supports the legacy
YAML scenario format while using the cleaned generic simulation primitives.

Example:
    python -m sim.run --config sim/scenarios/basic_economic.yaml
    python sim/run.py --config sim/scenarios/basic_economic.yaml --no-plot
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
SIM_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

from sim.engine.agents import BaseAgent, CautiousAgent, KellyAgent, MomentumAgent, RandomAgent
from sim.engine.environment import MarketEnvironment
from sim.engine.metrics import compute_extended_metrics, plot_results

logger = logging.getLogger(__name__)


AgentType = BaseAgent


def compute_metrics(history: list[float]) -> dict[str, float]:
    """Legacy wrapper for simple metrics."""
    if not history:
        return {"final_capital": 0.0, "total_return": 0.0, "max_drawdown": 0.0}

    try:
        metrics = compute_extended_metrics(history)
    except ValueError:
        return {
            "final_capital": float(history[-1]) if history else 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
        }

    return {
        "final_capital": metrics["final_capital"],
        "total_return": metrics["total_return"] * 100.0,
        "max_drawdown": metrics["max_drawdown"] * 100.0,
    }


def create_agent(cfg: Mapping[str, Any]) -> AgentType:
    """Create an agent from scenario config."""
    agent_type = str(cfg.get("type", "RandomAgent") or "RandomAgent").strip()

    params: dict[str, Any] = {
        "capital": float(cfg.get("capital", 1000.0)),
        "max_risk": float(cfg.get("max_risk", 0.02)),
    }

    if "seed" in cfg:
        params["seed"] = int(cfg["seed"])

    if agent_type == "KellyAgent":
        params["phi"] = float(cfg.get("phi", 0.25))
        if "p_success" in cfg:
            params["p_success"] = float(cfg["p_success"])
        return KellyAgent(**params)

    if agent_type == "RandomAgent":
        return RandomAgent(**params)

    if agent_type == "CautiousAgent":
        return CautiousAgent(**params)

    if agent_type == "MomentumAgent":
        return MomentumAgent(**params)

    raise ValueError(f"Unsupported agent type: {agent_type}")


def run_simulation(
    config_path: str | Path,
    *,
    plot: bool = True,
    output_plot: Optional[str | Path] = None,
) -> dict[str, dict[str, float]]:
    """Execute a simulation scenario and return per-agent metrics."""
    config = load_config(config_path)

    market_cfg = dict(config.get("market", {}) or {})
    simulation_cfg = dict(config.get("simulation", {}) or {})

    market = MarketEnvironment(
        volatility=float(market_cfg.get("volatility", 0.02)),
        drift=float(market_cfg.get("drift", 0.0)),
        lookback_period=int(market_cfg.get("lookback_period", 100)),
        initial_price=float(market_cfg.get("initial_price", 1.0)),
        shock_probability=float(market_cfg.get("shock_probability", 0.0)),
        shock_scale=float(market_cfg.get("shock_scale", 3.0)),
        seed=_optional_int(market_cfg.get("seed", simulation_cfg.get("seed"))),
    )

    agent_configs = config.get("agents", [])

    if not isinstance(agent_configs, list) or not agent_configs:
        logger.warning("Config has no agents list; using default KellyAgent + RandomAgent scenario.")
        initial_capital = float(simulation_cfg.get("initial_capital", 1000.0))
        agent_configs = [
            {
                "type": "KellyAgent",
                "capital": initial_capital,
                "max_risk": 0.02,
                "phi": 0.25,
            },
            {
                "type": "RandomAgent",
                "capital": initial_capital,
                "max_risk": 0.02,
            },
        ]

    agents = [create_agent(agent_cfg) for agent_cfg in agent_configs]
    
    steps = max(0, int(simulation_cfg.get("steps", 100)))

    for _ in range(steps):
        price_before = float(market.prices[-1])
        state = market.step_state()
        new_price = float(state.get("price", price_before))
        environment_return = (new_price - price_before) / price_before if price_before > 0 else 0.0

        for agent in agents:
            agent.act_and_update(state, environment_return)

    results: dict[str, list[float]] = {}
    metrics_by_agent: dict[str, dict[str, float]] = {}

    for index, agent in enumerate(agents):
        name = f"{type(agent).__name__}-{index}"
        metrics = compute_metrics(agent.history)
        logger.info("%s: %s", name, metrics)
        results[name] = list(agent.history)
        metrics_by_agent[name] = metrics

    if plot:
        class MarketView:
            def __init__(self, market_obj: MarketEnvironment) -> None:
                self.market = market_obj

        market_view = MarketView(market)

        plot_results(
            {
                name: (history, market_view)
                for name, history in results.items()
            },
            title=str(config.get("title", "BlackSwan Simulation Results")),
            output_file=output_plot,
            show=output_plot is None,
        )

    return metrics_by_agent


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load YAML scenario config."""
    path = Path(config_path)

    if not path.is_absolute() and not path.exists():
        candidate = SIM_DIR / path
        if candidate.exists():
            path = candidate

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"simulation config not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"failed to parse simulation config {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("simulation config must be a YAML mapping")

    return data


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="BlackSwan simulation runner")
    parser.add_argument(
        "--config",
        default=str(SIM_DIR / "scenarios" / "basic_economic.yaml"),
        help="Path to YAML scenario config",
    )
    parser.add_argument("--no-plot", action="store_true", help="Disable interactive plot display")
    parser.add_argument("--output-plot", default=None, help="Optional path to save plot image")
    args = parser.parse_args()

    try:
        run_simulation(
            args.config,
            plot=not args.no_plot or bool(args.output_plot),
            output_plot=args.output_plot,
        )
    except Exception as exc:
        logger.error("Simulation failed: %s", exc)
        raise SystemExit(1) from exc


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()