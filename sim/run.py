import argparse
import logging
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import yaml

from engine.agents import AgentType, KellyAgent, RandomAgent
from engine.environment import MarketEnvironment

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def compute_metrics(history: List[float]) -> Dict[str, float]:
    """
    Calculate financial metrics from agent capital history.

    Args:
        history: A sequence of capital values over simulation time steps.

    Returns:
        A dictionary containing final_capital, total_return, and max_drawdown.
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
        agents_data: Mapping of agent type names to their list of historical capital values.
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
    Factory method to instantiate agents based on configuration parameters.
    """
    agent_type = cfg.get("type")
    params = {
        "capital": float(cfg.get("capital", 1000.0)),
        "max_risk": float(cfg.get("max_risk", 0.02)),
    }

    if agent_type == "KellyAgent":
        params["phi"] = float(cfg.get("phi", 0.25))
        return KellyAgent(**params)
    if agent_type == "RandomAgent":
        return RandomAgent(**params)

    raise ValueError(f"Unknown agent type: {agent_type}")


def main() -> None:
    """
    Main simulation entry point handling argument parsing and simulation loop.
    """
    parser = argparse.ArgumentParser(description="Swarm-Sim economic simulator")
    parser.add_argument(
        "--config", default="scenarios/basic_economic.yaml", help="Path to YAML configuration file"
    )
    args = parser.parse_args()

    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logging.error(f"Failed to load config: {e}")
        return

    market = MarketEnvironment(
        volatility=config["market"]["volatility"],
        drift=config["market"].get("drift", 0.0),
    )

    agents: List[AgentType] = [create_agent(a) for a in config.get("agents", [])]

    for _ in range(config["simulation"]["steps"]):
        price_before = float(market.prices[-1])
        market_state = market.get_state()
        new_price = market.step()
        market_return = (new_price - price_before) / price_before if price_before != 0 else 0.0

        for agent in agents:
            fraction = agent.decide(market_state)
            agent.update(fraction * market_return)

    results = {}
    for agent in agents:
        name = type(agent).__name__
        metrics = compute_metrics(agent.history)
        logging.info(f"{name}: {metrics}")
        results[name] = agent.history
        agent.market = market

    plot_results(results)


if __name__ == "__main__":
    main()