import argparse
import yaml
from typing import Any, Dict, List, Union, Tuple

# Assuming these imports define the necessary classes for this specific runner.
# It's important to note that the `MarketEnvironment` and `Agent` interfaces
# inferred here might differ from those used in `multi_agent_sim.py` if
# they are sourced from different `engine` modules or versions.
# For this file, we assume `get_state` returns a float price, and `step` evolves
# the market and returns a new price, and agents decide based on a float price.
from engine.environment import MarketEnvironment
from engine.agents import KellyAgent, RandomAgent

# Define a type alias for readability, assuming these agents exist and match the inferred interface
AgentType = Union[KellyAgent, RandomAgent]


def compute_metrics(history: List[float]) -> Dict[str, float]:
    """
    Compute metrics from the agent's capital history.

    Args:
        history: List of capital values over time.

    Returns:
        Dictionary containing computed metrics.
    """
    metrics: Dict[str, float] = {
        "final_capital": history[-1],
        "total_return": (history[-1] - history[0]) / history[0] * 100,
        "max_drawdown": min((history[i] - max(history[:i+1])) / max(history[:i+1]) * 100 for i in range(1, len(history)))
    }
    return metrics


def plot_results(agents_data: Dict[str, Tuple[List[float], AgentType]]) -> None:
    """
    Plot the results of the simulation.

    Args:
        agents_data: Dictionary containing agent histories and agent objects.
    """
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))
    for name, (history, agent) in agents_data.items():
        plt.plot(history, label=name)

    plt.title("Agent Capital Over Time")
    plt.xlabel("Time Step")
    plt.ylabel("Capital")
    plt.legend()
    plt.grid(True)
    plt.show()


def main() -> None:
    """
    Main function to run the Swarm-Sim economic simulator.

    Parses configuration from a YAML file, initializes the market and agents,
    runs the simulation, and then computes and plots the results.
    """
    parser = argparse.ArgumentParser(description="Swarm-Sim economic simulator")
    parser.add_argument("--config", default="scenarios/basic_economic.yaml", help="Path to YAML config")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f)

    sim_cfg: Dict[str, Any] = config["simulation"]
    market_cfg: Dict[str, Any] = config["market"]
    agents_cfg: List[Dict[str, Any]] = config["agents"]

    # Initialize market
    # Assuming MarketEnvironment here has a `prices` attribute (list of floats)
    # and `get_state()` returns the current price (float), and `step()` advances and returns new price.
    market: MarketEnvironment = MarketEnvironment(volatility=market_cfg["volatility"], drift=market_cfg.get("drift", 0.0))

    # Initialize agents
    agents: List[AgentType] = []
    for ac in agents_cfg:
        agent_type: str = ac["type"]
        capital: float = float(ac["capital"]) # Ensure capital is float
        max_risk: float = float(ac.get("max_risk", 0.02)) # Ensure max_risk is float

        if agent_type == "KellyAgent":
            phi: float = float(ac.get("phi", 0.25)) # Ensure phi is float
            agents.append(KellyAgent(capital=capital, max_risk=max_risk, phi=phi))
        elif agent_type == "RandomAgent":
            agents.append(RandomAgent(capital=capital, max_risk=max_risk))
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    # Simulation loop
    num_steps: int = sim_cfg["steps"]
    for step in range(num_steps):
        # The agent's 'decide' method expects a float representing the current market state/price.
        market_state_for_decision: float = market.get_state()
        
        # Store initial market price for return calculation for this step *before* market evolves
        # Assuming market.prices is updated by market.step() or get_state() reflects latest.
        # market.prices[-1] accesses the last recorded price.
        price_before: float = market.prices[-1]
        
        # Move the market once for all agents in this step
        # Assuming market.step() evolves the market and returns the new price.
        new_price: float = market.step()
        market_return: float = (new_price - price_before) / price_before
        
        for agent in agents:
            # Agent decides based on the market state *before* the market's own evolution for this step.
            fraction: float = agent.decide(market_state_for_decision)
            
            # Agent's return: fraction of capital * (market price change percentage)
            agent_return: float = fraction * market_return
            agent.update(agent_return)

    # Collect metrics and display results
    # The dictionary stores agent histories and the agent object itself for further processing (e.g., plotting)
    agents_data: Dict[str, Tuple[List[float], AgentType]] = {}
    for agent in agents:
        name: str = type(agent).__name__
        metrics: Dict[str, float] = compute_metrics(agent.history)
        print(f"\n{name}:")
        for k, v in metrics.items():
            print(f"  {k}: {v:.4f}")
        agents_data[name] = (agent.history, agent)

    # Attach market reference to agents. This is likely for `plot_results`
    # to access market data via agent objects, maintaining original functionality.
    # This dynamically adds a 'market' attribute to each agent instance.
    for agent in agents:
        setattr(agent, 'market', market)

    plot_results(agents_data)

if __name__ == "__main__":
    main()