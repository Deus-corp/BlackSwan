#!/usr/bin/env python3
"""
Multi-Agent Simulator for BlackSwan TRL-4.
Simulates interactions between different agent types (e.g., Kelly-criterion based
and random agents) within a simplified market environment.
Uses core components: MarketEnvironment, ROIDispatcher, EventBus, GlobalState.
"""
import sys
import random
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Add root directory to sys.path for module imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Import BlackSwan core components
from sim.engine.environment import MarketEnvironment
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus


class RandomAgent:
    """
    A simple agent that makes random trading decisions within a maximum risk limit.
    """
    def __init__(self, capital: float, max_risk: float = 0.05) -> None:
        """
        Initializes the RandomAgent.

        Args:
            capital: The agent's initial capital.
            max_risk: The maximum fraction of capital the agent will risk per trade.
        """
        self.capital: float = capital
        self.max_risk: float = max_risk
        self.history: List[float] = [capital]

    def decide(self, market_state: Dict[str, Any]) -> float:
        """
        Makes a random decision for a trade fraction.

        Args:
            market_state: Current state of the market (unused by this agent).

        Returns:
            A float representing the fraction of capital to trade (positive for long, negative for short).
        """
        return random.uniform(-self.max_risk, self.max_risk)

    def update(self, trade_return: float) -> None:
        """
        Updates the agent's capital based on the trade return.

        Args:
            trade_return: The return on the last trade as a fraction.
        """
        self.capital *= (1 + trade_return)
        self.history.append(self.capital)


class AgentState:
    """
    Represents the state of an individual agent within the simulation.
    Combines agent-specific logic (ROIDispatcher or RandomAgent) with simulation-specific state.
    """
    def __init__(self, agent_id: int, initial_capital: float, is_kelly: bool) -> None:
        """
        Initializes an AgentState.

        Args:
            agent_id: Unique identifier for the agent.
            initial_capital: The starting capital for the agent.
            is_kelly: True if the agent uses a ROIDispatcher (Kelly-like), False for a RandomAgent.
        """
        self.id: int = agent_id
        self.capital: float = initial_capital
        self.is_kelly: bool = is_kelly
        self.alive: bool = True
        self.trades: int = 0
        self.total_return: float = 0.0
        self.history: List[float] = [initial_capital]

        # Conditionally initialize agent-specific logic components
        self.dispatcher: Optional[ROIDispatcher] = None
        self.random_agent: Optional[RandomAgent] = None


@dataclass
class SimulationConfig:
    """
    Configuration parameters for the MultiAgentSimulation.

    Attributes:
        num_agents: Total number of agents in the simulation.
        steps: Number of simulation steps (generations).
        initial_capital: Starting capital for each agent.
        drift: Market drift parameter for MarketEnvironment.
        volatility: Market volatility parameter for MarketEnvironment.
        burn_rate_per_step: Capital burn rate applied to each agent per step.
        agent_failure_prob: Probability of an agent failing randomly per step.
        shock_probability: Probability of a market shock occurring per step.
        shock_magnitude: Magnitude of market drift reduction during a shock.
        kelly_max_risk_per_trade: Maximum risk parameter for Kelly agents' ROIDispatcher.
        kelly_phi_llm: Phi LLM parameter for Kelly agents' ROIDispatcher.
        random_max_risk: Maximum risk parameter for Random agents.
        trade_leverage_factor: Multiplier for trade return calculation.
        trade_commission: Fixed commission deducted per trade.
    """
    num_agents: int = 6
    steps: int = 200
    initial_capital: float = 1000.0
    drift: float = 0.002
    volatility: float = 0.01
    burn_rate_per_step: float = 0.5
    agent_failure_prob: float = 0.0
    shock_probability: float = 0.0
    shock_magnitude: float = 0.3
    kelly_max_risk_per_trade: float = 0.05
    kelly_phi_llm: float = 0.15
    random_max_risk: float = 0.05
    trade_leverage_factor: float = 0.1 # This was a magic number in original code
    trade_commission: float = 1.0 # This was a magic number in original code


class MultiAgentSimulation:
    """
    Manages the multi-agent simulation, including market environment, agents,
    and their interactions over time.
    """
    def __init__(self, config: SimulationConfig) -> None:
        """
        Initializes the MultiAgentSimulation with a given configuration.

        Args:
            config: An instance of SimulationConfig specifying simulation parameters.
        """
        self.config: SimulationConfig = config
        self.market: MarketEnvironment = MarketEnvironment(
            volatility=config.volatility, drift=config.drift
        )
        self.event_bus: EventBus = EventBus()
        self.global_state: GlobalState = GlobalState()
        self.agents: List[AgentState] = []

        # Initialize global treasury balance
        self.global_state.update(
            "economic_state",
            {"treasury_balance": {"USDC": self.config.initial_capital * self.config.num_agents}},
        )

    def setup_agents(self) -> None:
        """
        Configures and initializes all agents based on the simulation configuration.
        Divides agents into Kelly-criterion based and random agents.
        """
        n: int = self.config.num_agents
        # Calculate how many agents should be Kelly-type (roughly half)
        kelly_count: int = n // 2 + n % 2

        for i in range(n):
            is_kelly: bool = i < kelly_count
            agent_state = AgentState(i, self.config.initial_capital, is_kelly)

            if is_kelly:
                # Kelly agents use ROIDispatcher with configurable parameters
                agent_state.dispatcher = ROIDispatcher(
                    config={
                        "max_risk_per_trade": self.config.kelly_max_risk_per_trade,
                        "phi_llm": self.config.kelly_phi_llm,
                    }
                )
            else:
                # Random agents use the simple RandomAgent logic
                agent_state.random_agent = RandomAgent(
                    self.config.initial_capital, max_risk=self.config.random_max_risk
                )
            self.agents.append(agent_state)

    def apply_shocks(self) -> None:
        """
        Applies random market shocks (reduces market drift) and agent failures.
        """
        if random.random() < self.config.shock_probability:
            # Market drift is temporarily reduced during a shock
            self.market.drift *= (1 - self.config.shock_magnitude)

        for agent in self.agents:
            if agent.alive and random.random() < self.config.agent_failure_prob:
                agent.alive = False

    def step(self) -> None:
        """
        Executes a single simulation step for all active agents.
        Includes market updates, agent decisions, capital burn, and trade execution.
        """
        self.apply_shocks()
        market_state: Dict[str, Any] = self.market.get_state()
        price: float = market_state.get("price", 1.0) # Default price to 1.0 to avoid division by zero if key missing

        for agent in self.agents:
            if not agent.alive:
                continue

            # Apply capital burn rate
            agent.capital -= self.config.burn_rate_per_step
            if agent.capital <= 0:
                agent.alive = False
                continue

            fraction: float = 0.0
            if agent.is_kelly:
                # Kelly agent decision: evaluate market state with ROIDispatcher
                if agent.dispatcher: # Ensure dispatcher is initialized
                    fraction, _ = agent.dispatcher.evaluate(market_state, agent.capital)
            else:
                # Random agent decision
                if agent.random_agent: # Ensure random_agent is initialized
                    fraction = agent.random_agent.decide(market_state)

            # Execute trade (simplified)
            # The trade_leverage_factor (0.1) was a magic number; now configurable
            ret: float = price * fraction * self.config.trade_leverage_factor
            agent.capital *= (1 + ret)
            agent.capital -= self.config.trade_commission  # Fixed commission per trade

            agent.trades += 1
            agent.total_return += ret
            agent.history.append(agent.capital)

            if agent.capital <= 0:
                agent.alive = False

    def run(self) -> Dict[str, float]:
        """
        Runs the full simulation for the specified number of steps.

        Returns:
            A dictionary containing various metrics from the simulation.
        """
        self.setup_agents()
        for _ in range(self.config.steps):
            self.step()
        return self.collect_metrics()

    def collect_metrics(self) -> Dict[str, float]:
        """
        Collects and calculates key performance metrics at the end of the simulation.

        Returns:
            A dictionary of simulation metrics.
        """
        alive_agents: List[AgentState] = [a for a in self.agents if a.alive]
        kelly_agents: List[AgentState] = [a for a in self.agents if a.is_kelly]
        random_agents: List[AgentState] = [a for a in self.agents if not a.is_kelly]

        survival_rate: float = len(alive_agents) / self.config.num_agents if self.config.num_agents > 0 else 0.0
        
        kelly_avg_capital: float = statistics.mean([a.capital for a in kelly_agents]) if kelly_agents else 0.0
        random_avg_capital: float = statistics.mean([a.capital for a in random_agents]) if random_agents else 0.0

        metrics: Dict[str, float] = {
            "steps": float(self.config.steps),
            "num_agents": float(self.config.num_agents),
            "agents_alive": float(len(alive_agents)),
            "survival_rate": survival_rate,
            "kelly_avg_capital": kelly_avg_capital,
            "random_avg_capital": random_avg_capital,
            "total_trades": float(sum(a.trades for a in self.agents)),
        }
        return metrics


if __name__ == "__main__":
    # Example usage of the simulation
    simulation_config: SimulationConfig = SimulationConfig(
        num_agents=6,
        steps=100,
        agent_failure_prob=0.02,
        # Customize new parameters
        kelly_max_risk_per_trade=0.07,
        kelly_phi_llm=0.2,
        random_max_risk=0.03,
        trade_leverage_factor=0.15,
        trade_commission=0.5,
    )
    sim = MultiAgentSimulation(simulation_config)
    simulation_metrics: Dict[str, float] = sim.run()

    print("\n--- Simulation Results ---")
    for k, v in simulation_metrics.items():
        print(f"{k}: {v:.4f}")

    # Optional: Print final capital for each agent
    # print("\n--- Agent Final Capitals ---")
    # for agent in sim.agents:
    #     status = "Alive" if agent.alive else "Dead"
    #     agent_type = "Kelly" if agent.is_kelly else "Random"
    #     print(f"Agent {agent.id} ({agent_type}, {status}): Capital={agent.capital:.2f}, Trades={agent.trades}")