import argparse
import yaml
from typing import Any, Dict, List, Union

# Assuming these imports define the necessary classes
from engine.environment import MarketEnvironment
from engine.agents import KellyAgent, RandomAgent  # Assuming these are the concrete agent classes
from engine.metrics import compute_metrics, plot_results

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
    market = MarketEnvironment(volatility=market_cfg["volatility"], drift=market_cfg.get("drift", 0.0))

    # Initialize agents
    # Agents could be KellyAgent or RandomAgent. Using Union for type hinting.
    AgentType = Union[KellyAgent, RandomAgent]  # Define a type alias for readability
    agents: List[AgentType] = []
    for ac in agents_cfg:
        agent_type: str = ac["type"]
        capital: float = ac["capital"]
        max_risk: float = ac.get("max_risk", 0.02)

        if agent_type == "KellyAgent":
            phi: float = ac.get("phi", 0.25)
            agents.append(KellyAgent(capital=capital, max_risk=max_risk, phi=phi))
        elif agent_type == "RandomAgent":
            agents.append(RandomAgent(capital=capital, max_risk=max_risk))
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    # Simulation loop
    num_steps: int = sim_cfg["steps"]
    for step in range(num_steps):
        market_state: float = market.get_state()
        
        # Store initial market price to calculate return for this step
        price_before: float = market.prices[-1]
        
        # Move the market once for all agents in this step
        new_price: float = market.step()
        market_return: float = (new_price - price_before) / price_before
        
        for agent in agents:
            fraction: float = agent.decide(market_state)
            # Agent's return: fraction * (market price change)
            agent_return: float = fraction * market_return
            agent.update(agent_return)

    # Collect metrics and display results
    agents_data: Dict[str, tuple[List[float], AgentType]] = {}
    for agent in agents:
        name: str = type(agent).__name__
        metrics: Dict[str, float] = compute_metrics(agent.history)
        print(f"\n{name}:")
        for k, v in metrics.items():
            print(f"  {k}: {v:.4f}")
        agents_data[name] = (agent.history, agent)

    # Attach market reference to agents. This is likely for `plot_results`
    # to access market data via agent objects, maintaining original functionality.
    for agent in agents:
        # Assuming agent classes are designed to accept this attribute,
        # or it's a dynamic addition for post-simulation analysis/plotting.
        setattr(agent, 'market', market)

    plot_results(agents_data)

if __name__ == "__main__":
    main()