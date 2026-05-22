import argparse
import logging
from typing import Any, Dict, List, Tuple

import yaml
import matplotlib.pyplot as plt

from engine.environment import MarketEnvironment
from engine.agents import KellyAgent, RandomAgent, AgentType

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def compute_metrics(history: List[float]) -> Dict[str, float]:
    """
    Calculate financial metrics from agent capital history.

    Args:
        history: List of capital values over time.

    Returns:
        Dictionary containing final_capital, total_return, and max_drawdown.
    """
    if not history:
        return {"final_capital": 0.0, "total_return": 0.0, "max_drawdown": 0.0}

    peak = history[0]
    max_drawdown = 0.0
    for capital in history:
        if capital > peak:
            peak = capital
        drawdown = (capital - peak) / peak
        if drawdown < max_drawdown:
            max_drawdown = drawdown

    return {
        "final_capital": history[-1],
        "total_return": (history[-1] - history[0]) / history[0] * 100,
        "max_drawdown": max_drawdown * 100
    }

def plot_results(agents_data: Dict[str, List[float]]) -> None:
    """
    Visualize agent capital evolution.

    Args:
        agents_data: Mapping of agent names to their history lists.
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
    """Factory method to instantiate agents based on configuration."""
    agent_type = cfg["type"]
    params = {
        "capital": float(cfg.get("capital", 1000.0)),
        "max_risk": float(cfg.get("max_risk", 0.02))
    }
    
    if agent_type == "KellyAgent":
        params["phi"] = float(cfg.get("phi", 0.25))
        return KellyAgent(**params)
    elif agent_type == "RandomAgent":
        return RandomAgent(**params)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

def main() -> None:
    """Main simulation entry point."""
    parser = argparse.ArgumentParser(description="Swarm-Sim economic simulator")
    parser.add_argument("--config", default="scenarios/basic_economic.yaml", help="Path to YAML config")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f)

    market = MarketEnvironment(
        volatility=config["market"]["volatility"],
        drift=config["market"].get("drift", 0.0)
    )
    
    agents = [create_agent(a) for a in config["agents"]]

    for _ in range(config["simulation"]["steps"]):
        price_before = float(market.prices[-1])
        market_state = market.get_state()
        new_price = market.step()
        market_return = (new_price - price_before) / price_before
        
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