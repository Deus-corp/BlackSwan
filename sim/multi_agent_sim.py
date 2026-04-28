#!/usr/bin/env python3
"""
Многоагентный симулятор для BlackSwan TRL-4.
Использует реальные компоненты: MarketEnvironment, ROIDispatcher, EventBus, GlobalState.
"""
import sys, os, random, statistics
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sim.engine.environment import MarketEnvironment
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus

class RandomAgent:
    def __init__(self, capital, max_risk=0.05):
        self.capital = capital
        self.max_risk = max_risk
        self.history = [capital]
    def decide(self, market_state):
        return random.uniform(-self.max_risk, self.max_risk)
    def update(self, trade_return):
        self.capital *= (1 + trade_return)
        self.history.append(self.capital)

class AgentState:
    def __init__(self, agent_id, capital, is_kelly=True):
        self.id = agent_id
        self.capital = capital
        self.is_kelly = is_kelly
        self.alive = True
        self.trades = 0
        self.total_return = 0.0
        self.history = [capital]

class SimulationConfig:
    def __init__(self, num_agents=6, steps=200, initial_capital=1000.0,
                 drift=0.002, volatility=0.01, burn_rate_per_step=0.5,
                 agent_failure_prob=0.0, shock_probability=0.0, shock_magnitude=0.3):
        self.num_agents = num_agents
        self.steps = steps
        self.initial_capital = initial_capital
        self.drift = drift
        self.volatility = volatility
        self.burn_rate_per_step = burn_rate_per_step
        self.agent_failure_prob = agent_failure_prob
        self.shock_probability = shock_probability
        self.shock_magnitude = shock_magnitude

class MultiAgentSimulation:
    def __init__(self, config):
        self.config = config
        self.market = MarketEnvironment(volatility=config.volatility, drift=config.drift)
        self.event_bus = EventBus()
        self.global_state = GlobalState()
        self.agents = []
        self.global_state.update("economic_state", {"treasury_balance": {"USDC": config.initial_capital * config.num_agents}})

    def setup_agents(self):
        n = self.config.num_agents
        kelly_count = n // 2 + n % 2
        for i in range(n):
            is_kelly = i < kelly_count
            agent = AgentState(i, self.config.initial_capital, is_kelly)
            if is_kelly:
                agent.dispatcher = ROIDispatcher(config={"max_risk_per_trade": 0.05, "phi_llm": 0.15})
            else:
                agent.random_agent = RandomAgent(self.config.initial_capital, max_risk=0.05)
            self.agents.append(agent)

    def apply_shocks(self):
        if random.random() < self.config.shock_probability:
            self.market.drift *= (1 - self.config.shock_magnitude)
        for agent in self.agents:
            if agent.alive and random.random() < self.config.agent_failure_prob:
                agent.alive = False

    def step(self):
        self.apply_shocks()
        market_state = self.market.get_state()
        price = market_state["price"]
        for agent in self.agents:
            if not agent.alive:
                continue
            agent.capital -= self.config.burn_rate_per_step
            if agent.capital <= 0:
                agent.alive = False
                continue
            if agent.is_kelly:
                fraction, _ = agent.dispatcher.evaluate(market_state, agent.capital)
            else:
                fraction = agent.random_agent.decide(market_state)
            # Исполнение сделки (упрощённо)
            ret = price * fraction * 0.1
            agent.capital *= (1 + ret)
            agent.capital -= 1.0  # фиксированная комиссия
            agent.trades += 1
            agent.total_return += ret
            agent.history.append(agent.capital)
            if agent.capital <= 0:
                agent.alive = False

    def run(self):
        self.setup_agents()
        for _ in range(self.config.steps):
            self.step()
        return self.collect_metrics()

    def collect_metrics(self):
        alive = [a for a in self.agents if a.alive]
        metrics = {
            "steps": self.config.steps,
            "num_agents": self.config.num_agents,
            "agents_alive": len(alive),
            "survival_rate": len(alive)/self.config.num_agents,
            "kelly_avg_capital": statistics.mean([a.capital for a in self.agents if a.is_kelly]),
            "random_avg_capital": statistics.mean([a.capital for a in self.agents if not a.is_kelly]),
            "total_trades": sum(a.trades for a in self.agents),
        }
        return metrics

if __name__ == "__main__":
    config = SimulationConfig(num_agents=6, steps=100, agent_failure_prob=0.02)
    sim = MultiAgentSimulation(config)
    metrics = sim.run()
    for k, v in metrics.items():
        print(f"{k}: {v}")