import argparse
import logging
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import yaml

from engine.agents import AgentType, KellyAgent, RandomAgent
from engine.environment import MarketEnvironment

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def compute_metrics(history: List[float]) -> Dict[str, float]:
    """
    Calculate financial performance metrics from a capital history series.

    Args:
        history: A list of float values representing capital over time.

    Returns:
        A dictionary containing 'final_capital', 'total_return' (percentage), 
        and 'max_drawdown' (percentage).
    """
    if not history:
        return {"final_capital": 0.0, "total_return": 0.0, "max_drawdown": 0.0}

    peak = history[0]
    max_drawdown = 0.0
    for capital in history:
        if capital > peak:
            peak = capital
        drawdown = (capital - peak) / peak if peak > 0 else 0.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown

    return {
        "final_capital": float(history[-1]),
        "total_return": (history[-1] - history[0]) / history[0] * 100 if history[0] != 0 else 0.0,
        "max_drawdown": max_drawdown * 100,
    }


def plot_results(agents_data: Dict[str, List[float]]) -> None:
    """
    Visualize the capital evolution for each agent.

    Args:
        agents_data: Mapping of agent names to their historical capital sequences.
    """
    plt.figure(figsize=(10, 6))
    for name, history in agents_data.items():
        plt.plot(history, label=name)
    plt.title("Agent Capital Over Time")
    plt.xlabel("Time Step")
    plt.ylabel("Capital")
    plt.legend()
    plt.grid(True)
    plt.show()


def create_agent(cfg: Dict[str, Any]) -> AgentType:
    """
    Factory method to instantiate an agent instance based on configuration data.

    Args:
        cfg: Dictionary containing agent configuration (type, capital, params).

    Returns:
        An instance of an agent conforming to AgentType.

    Raises:
        ValueError: If an unsupported agent type is requested.
    """
    agent_type = cfg.get("type")
    params: Dict[str, Any] = {
        "capital": float(cfg.get("capital", 1000.0)),
        "max_risk": float(cfg.get("max_risk", 0.02)),
    }

    if agent_type == "KellyAgent":
        params["phi"] = float(cfg.get("phi", 0.25))
        return KellyAgent(**params)
    if agent_type == "RandomAgent":
        return RandomAgent(**params)

    raise ValueError(f"Unsupported agent type: {agent_type}")


def run_simulation(config_path: str) -> None:
    """
    Executes the market simulation based on the provided configuration file path.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logging.error(f"Failed to load simulation config from {config_path}: {e}")
        return

    market = MarketEnvironment(
        volatility=float(config["market"]["volatility"]),
        drift=float(config["market"].get("drift", 0.0)),
    )

    agents: List[AgentType] = [create_agent(a) for a in config.get("agents", [])]

    # Main simulation loop
    for _ in range(int(config["simulation"]["steps"] or 0)):
        price_before = float(market.prices[-1])
        market_state = market.get_state()
        new_price = market.step()
        market_return = (new_price - price_before) / price_before if price_before != 0 else 0.0

        for agent in agents:
            fraction = agent.decide(market_state)
            agent.update(fraction * market_return)

    # Post-simulation aggregation
    results: Dict[str, List[float]] = {}
    for agent in agents:
        name = type(agent).__name__
        metrics = compute_metrics(agent.history)
        logging.info(f"{name}: {metrics}")
        results[name] = agent.history
        agent.market = market

    plot_results(results)


def main() -> None:
    """
    Entry point for the simulation CLI.
    """
    parser = argparse.ArgumentParser(description="Swarm-Sim economic simulator")
    parser.add_argument(
        "--config", 
        default="scenarios/basic_economic.yaml", 
        help="Path to YAML configuration file"
    )
    args = parser.parse_args()

    run_simulation(args.config)


if __name__ == "__main__":
    main()