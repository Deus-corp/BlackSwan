#!/usr/bin/env python3
"""Multi-agent simulation harness for BlackSwan autonomous swarm experiments.

This file is intentionally a simulation/experiment runner, not core runtime.
It preserves the legacy Kelly-vs-random economic experiment while making the
model more generic and compatible with the updated `MarketEnvironment`.

The simulation can be used to test:
- resource survival under burn and shocks,
- policy performance across many agents,
- ROI dispatcher behavior,
- stochastic baseline comparisons,
- future non-trading swarm policies.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.engine.environment import MarketEnvironment
from src.core.event_bus import EventBus
from src.core.global_state import GlobalState
from src.economy.roi_dispatcher import ROIDispatcher


@dataclass(slots=True)
class RandomAgent:
    """Stochastic baseline agent with bounded action intensity."""

    capital: float
    max_risk: float = 0.05
    seed: Optional[int] = None
    history: list[float] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if not (0.0 <= self.max_risk <= 1.0):
            raise ValueError("max_risk must be in [0, 1]")
        self._rng = random.Random(self.seed)
        self.history = [float(self.capital)]

    def decide(self, market_state: dict[str, Any]) -> float:
        """Return random action intensity."""
        del market_state
        return self._rng.uniform(-self.max_risk, self.max_risk)

    def update(self, trade_return: float) -> None:
        """Update capital by return fraction."""
        self.capital = max(0.0, self.capital * (1.0 + float(trade_return)))
        self.history.append(self.capital)


@dataclass(slots=True)
class AgentState:
    """Individual simulated agent state."""

    id: int
    initial_capital: float
    is_kelly: bool
    capital: float = 0.0
    alive: bool = True
    trades: int = 0
    total_return: float = 0.0
    history: list[float] = field(default_factory=list)
    dispatcher: Optional[ROIDispatcher] = None
    random_agent: Optional[RandomAgent] = None
    last_action: float = 0.0
    last_reason: str = "initialized"

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        self.capital = float(self.initial_capital)
        self.history = [self.capital]

    def mark_dead(self, reason: str) -> None:
        self.alive = False
        self.last_reason = reason


@dataclass(slots=True)
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
    seed: Optional[int] = None
    emit_events: bool = False

    def validate(self) -> None:
        if self.num_agents <= 0:
            raise ValueError("num_agents must be positive")
        if self.steps < 0:
            raise ValueError("steps must be non-negative")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.volatility < 0:
            raise ValueError("volatility must be non-negative")
        if self.burn_rate_per_step < 0:
            raise ValueError("burn_rate_per_step must be non-negative")
        if not (0.0 <= self.agent_failure_prob <= 1.0):
            raise ValueError("agent_failure_prob must be in [0, 1]")
        if not (0.0 <= self.shock_probability <= 1.0):
            raise ValueError("shock_probability must be in [0, 1]")
        if self.shock_magnitude < 0:
            raise ValueError("shock_magnitude must be non-negative")


class MultiAgentSimulation:
    """Orchestrates stochastic environment and multiple autonomous agents."""

    def __init__(self, config: SimulationConfig) -> None:
        config.validate()
        self.config = config
        self._rng = random.Random(config.seed)

        self.market = MarketEnvironment(
            volatility=config.volatility,
            drift=config.drift,
            shock_probability=config.shock_probability,
            shock_scale=max(1.0, 1.0 + config.shock_magnitude),
            seed=config.seed,
        )
        self.event_bus = EventBus()
        self.global_state = GlobalState()
        self.agents: list[AgentState] = []
        self.current_step = 0
        self.created_at = time.time()

        self.global_state.update(
            "economic_state",
            {
                "treasury_balance": {
                    "USDC": self.config.initial_capital * self.config.num_agents,
                },
                "simulation_started_at": self.created_at,
            },
        )

    def setup_agents(self) -> None:
        """Instantiate agents with configured strategy mix."""
        if self.agents:
            return

        kelly_count = self.config.num_agents // 2 + (self.config.num_agents % 2)

        for index in range(self.config.num_agents):
            is_kelly = index < kelly_count
            agent = AgentState(index, self.config.initial_capital, is_kelly)

            if is_kelly:
                agent.dispatcher = ROIDispatcher(
                    {
                        "max_risk_per_trade": self.config.kelly_max_risk_per_trade,
                        "phi_llm": self.config.kelly_phi_llm,
                    }
                )
            else:
                agent.random_agent = RandomAgent(
                    self.config.initial_capital,
                    self.config.random_max_risk,
                    seed=None if self.config.seed is None else self.config.seed + index,
                )

            self.agents.append(agent)

    def apply_shocks_and_burn(self) -> None:
        """Apply operational burn and stochastic agent failures."""
        for agent in self.agents:
            if not agent.alive:
                continue

            agent.capital = max(0.0, agent.capital - self.config.burn_rate_per_step)

            if agent.capital <= 0:
                agent.mark_dead("resources_depleted")
                continue

            if self._rng.random() < self.config.agent_failure_prob:
                agent.mark_dead("stochastic_failure")

    def step(self) -> None:
        """Process one full cycle of environment dynamics and agent actions."""
        market_state = self.market.step_state()
        price = float(market_state.get("price", 1.0))

        self.apply_shocks_and_burn()

        for agent in self.agents:
            if not agent.alive:
                continue

            fraction = self._agent_action(agent, market_state)
            fraction = self._clamp_action(fraction)
            agent.last_action = fraction

            trade_return = price * fraction * self.config.trade_leverage_factor
            agent.capital = max(0.0, agent.capital * (1.0 + trade_return) - self.config.trade_commission)
            agent.trades += 1
            agent.total_return += trade_return
            agent.history.append(agent.capital)

            if agent.random_agent is not None:
                agent.random_agent.capital = agent.capital
                agent.random_agent.history.append(agent.capital)

            if agent.capital <= 0:
                agent.mark_dead("capital_depleted_after_action")

        self.current_step += 1
        self._update_global_state(market_state)

    def collect_metrics(self) -> dict[str, float]:
        """Aggregate simulation performance metrics."""
        alive_agents = [agent for agent in self.agents if agent.alive]
        kelly_agents = [agent for agent in self.agents if agent.is_kelly]
        random_agents = [agent for agent in self.agents if not agent.is_kelly]

        total_capital = sum(agent.capital for agent in self.agents)
        initial_total = self.config.initial_capital * self.config.num_agents

        return {
            "steps": float(self.current_step),
            "configured_steps": float(self.config.steps),
            "num_agents": float(self.config.num_agents),
            "agents_alive": float(len(alive_agents)),
            "survival_rate": len(alive_agents) / self.config.num_agents,
            "kelly_avg_capital": self._mean_capital(kelly_agents),
            "random_avg_capital": self._mean_capital(random_agents),
            "total_capital": total_capital,
            "total_return": (total_capital / initial_total) - 1.0 if initial_total > 0 else 0.0,
            "total_trades": float(sum(agent.trades for agent in self.agents)),
            "market_price": float(self.market.get_state().get("price", 0.0)),
            "market_volatility_estimate": float(self.market.get_state().get("volatility_estimate", 0.0)),
        }

    def run(self) -> dict[str, float]:
        """Execute full simulation pipeline."""
        self.setup_agents()

        for _ in range(self.config.steps):
            if not any(agent.alive for agent in self.agents):
                break
            self.step()

        return self.collect_metrics()

    def snapshot(self) -> dict[str, Any]:
        """Return serializable simulation state."""
        return {
            "config": {
                "num_agents": self.config.num_agents,
                "steps": self.config.steps,
                "initial_capital": self.config.initial_capital,
                "drift": self.config.drift,
                "volatility": self.config.volatility,
                "burn_rate_per_step": self.config.burn_rate_per_step,
                "agent_failure_prob": self.config.agent_failure_prob,
                "shock_probability": self.config.shock_probability,
                "shock_magnitude": self.config.shock_magnitude,
            },
            "metrics": self.collect_metrics(),
            "market": self.market.get_state(),
            "agents": [
                {
                    "id": agent.id,
                    "capital": agent.capital,
                    "alive": agent.alive,
                    "is_kelly": agent.is_kelly,
                    "trades": agent.trades,
                    "total_return": agent.total_return,
                    "last_action": agent.last_action,
                    "last_reason": agent.last_reason,
                }
                for agent in self.agents
            ],
        }

    def _agent_action(self, agent: AgentState, market_state: dict[str, Any]) -> float:
        if agent.is_kelly and agent.dispatcher is not None:
            fraction, _ = agent.dispatcher.evaluate(market_state, agent.capital)
            return float(fraction)

        if agent.random_agent is not None:
            return float(agent.random_agent.decide(market_state))

        return 0.0

    def _update_global_state(self, market_state: dict[str, Any]) -> None:
        self.global_state.update(
            "simulation_state",
            {
                "step": self.current_step,
                "market": dict(market_state),
                "metrics": self.collect_metrics(),
            },
        )

    def _clamp_action(self, value: float) -> float:
        if not isinstance(value, (int, float)):
            return 0.0
        if value != value:
            return 0.0

        max_abs = max(
            self.config.kelly_max_risk_per_trade,
            self.config.random_max_risk,
            0.0,
        )
        return max(-max_abs, min(max_abs, float(value)))

    @staticmethod
    def _mean_capital(agents: list[AgentState]) -> float:
        return statistics.fmean(agent.capital for agent in agents) if agents else 0.0


if __name__ == "__main__":
    sim_config = SimulationConfig(
        num_agents=10,
        steps=200,
        agent_failure_prob=0.01,
        shock_probability=0.1,
        seed=42,
    )
    simulation = MultiAgentSimulation(sim_config)
    results = simulation.run()
    print(f"Results: {results}")