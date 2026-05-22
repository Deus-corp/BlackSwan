#!/usr/bin/env python3
"""
Multi-Agent Simulator for BlackSwan TRL-4.
Simulates interactions between Kelly-criterion and stochastic trading agents.
"""

import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure root access for core component imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim.engine.environment import MarketEnvironment
from src.core.event_bus import EventBus
from src.core.global_state import GlobalState
from src.economy.roi_dispatcher import ROIDispatcher


class RandomAgent:
    """Stochastic trader with basic risk appetite bounds."""
    def __init__(self, capital: float, max_risk: float = 0.05) -> None:
        self.capital = capital
        self.max_risk = max_risk
        self.history: List[float] = [capital]

    def decide(self, market_state: Dict[str, Any]) -> float:
        """Returns a trade fraction sampled from uniform distribution [-max_risk, max_risk]."""
        return random.uniform(-self.max_risk, self.max_risk)

    def update(self, trade_return: float) -> None:
        """Updates capital based on return fraction."""
        self.capital *= (1.0 + trade_return)
        self.history.append(self.capital)


class AgentState:
    """Container for individual agent lifecycle and strategy execution."""
    def __init__(self, agent_id: int, initial_capital: float, is_kelly: bool) -> None:
        self.id = agent_id
        self.capital = initial_capital
        self.is_kelly = is_kelly
        self.alive = True
        self.trades = 0
        self.total_return = 0.0
        self.history: List[float] = [initial_capital]
        self.dispatcher: Optional[ROIDispatcher] = None
        self.random_agent: Optional[RandomAgent] = None


@dataclass
class SimulationConfig:
    """Configuration schema for multi-agent simulation behavior."""
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
    trade_leverage_factor: float = 0.1
    trade_commission: float = 1.0


class MultiAgentSimulation:
    """Orchestrator for the market environment and agent interactions."""
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.market = MarketEnvironment(volatility=config.volatility, drift=config.drift)
        self.event_bus = EventBus()
        self.global_state = GlobalState()
        self.agents: List[AgentState] = []
        self.global_state.update(
            "economic_state",
            {"treasury_balance": {"USDC": self.config.initial_capital * self.config.num_agents}},
        )

    def setup_agents(self) -> None:
        """Instantiates agents with specific strategies based on simulation configuration."""
        kelly_count = self.config.num_agents // 2 + (self.config.num_agents % 2)
        for i in range(self.config.num_agents):
            is_kelly = i < kelly_count
            agent = AgentState(i, self.config.initial_capital, is_kelly)
            if is_kelly:
                agent.dispatcher = ROIDispatcher({
                    "max_risk_per_trade": self.config.kelly_max_risk_per_trade,
                    "phi_llm": self.config.kelly_phi_llm,
                })
            else:
                agent.random_agent = RandomAgent(self.config.initial_capital, self.config.random_max_risk)
            self.agents.append(agent)

    def apply_shocks_and_burn(self) -> None:
        """Applies environmental volatility, market shocks, and operational burn to agents."""
        if random.random() < self.config.shock_probability:
            self.market.drift *= (1.0 - self.config.shock_magnitude)

        for agent in self.agents:
            if not agent.alive: continue
            agent.capital -= self.config.burn_rate_per_step
            if agent.capital <= 0 or random.random() < self.config.agent_failure_prob:
                agent.alive = False

    def step(self) -> None:
        """Processes one full cycle of market dynamics and agent trading actions."""
        self.market.evolve()
        market_state = self.market.get_state()
        price = float(market_state.get("price", 1.0))

        self.apply_shocks_and_burn()

        for agent in self.agents:
            if not agent.alive: continue
            fraction = 0.0
            if agent.is_kelly and agent.dispatcher:
                fraction, _ = agent.dispatcher.evaluate(market_state, agent.capital)
            elif agent.random_agent:
                fraction = agent.random_agent.decide(market_state)

            ret = price * fraction * self.config.trade_leverage_factor
            agent.capital = agent.capital * (1.0 + ret) - self.config.trade_commission
            agent.trades += 1
            agent.total_return += ret
            agent.history.append(agent.capital)
            if agent.capital <= 0: agent.alive = False

    def collect_metrics(self) -> Dict[str, float]:
        """Aggregates simulation performance metrics."""
        alive_agents = [a for a in self.agents if a.alive]
        kelly = [a for a in self.agents if a.is_kelly]
        rand = [a for a in self.agents if not a.is_kelly]

        return {
            "steps": float(self.config.steps),
            "num_agents": float(self.config.num_agents),
            "agents_alive": float(len(alive_agents)),
            "survival_rate": len(alive_agents) / self.config.num_agents if self.config.num_agents else 0.0,
            "kelly_avg_capital": statistics.mean([a.capital for a in kelly]) if kelly else 0.0,
            "random_avg_capital": statistics.mean([a.capital for a in rand]) if rand else 0.0,
            "total_trades": float(sum(a.trades for a in self.agents)),
        }

    def run(self) -> Dict[str, float]:
        """Executes full simulation pipeline."""
        self.setup_agents()
        for _ in range(self.config.steps):
            self.step()
        return self.collect_metrics()


if __name__ == "__main__":
    config = SimulationConfig(num_agents=10, steps=200, agent_failure_prob=0.01, shock_probability=0.1)
    sim = MultiAgentSimulation(config)
    results = sim.run()
    print(f"Results: {results}")