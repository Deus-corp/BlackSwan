#!/usr/bin/env python3
import sys, os, asyncio, random
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from sim.engine.environment import MarketEnvironment
from src.core.global_state import GlobalState
from src.core.event_bus import EventBus
from src.economy.roi_dispatcher import ROIDispatcher
from src.core.ipfs_client import IPFSClient
from mvp.sandbox import execute_in_sandbox

INITIAL_CAPITAL = 1000.0
SIMULATION_STEPS = 200   # для демонстрации; можно увеличить позже
VOLATILITY = 0.01
DRIFT = 0.002   # был 0.001

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

async def main():
    market = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)
    event_bus = EventBus()
    dispatcher = ROIDispatcher(config={"max_risk_per_trade": 0.05, "phi_llm": 0.15})
    ipfs = IPFSClient()
    state = GlobalState()

    kelly_capital = INITIAL_CAPITAL
    kelly_history = [INITIAL_CAPITAL]
    random_agent = RandomAgent(INITIAL_CAPITAL, max_risk=0.05)
    kelly_fractions = []

    state.update("economic_state", {"treasury_balance": {"USDC": kelly_capital}})
    print(f"Начальный капитал: {INITIAL_CAPITAL:.2f} | Рынок: DRIFT={DRIFT}, VOL={VOLATILITY}")
    print("─" * 60)

    for step in range(1, SIMULATION_STEPS + 1):
        market_state = market.get_state()
        price = market_state["price"]

        # Kelly принимает решение (какую долю инвестировать)
        fraction, _ = dispatcher.evaluate(market_state, kelly_capital)
        kelly_fractions.append(fraction)

        # Следующее значение рынка
        new_price = market.step()
        market_return = (new_price - price) / price

        # Генерируем код сделки для песочницы
        # Kelly-агент инвестирует fraction * market_return
        code = f"print({fraction} * {market_return})"
        exit_code, stdout, stderr = execute_in_sandbox(code, timeout=5)

        if exit_code == 0 and stdout.strip():
            try:
                kelly_return = float(stdout.strip())
            except ValueError:
                kelly_return = 0.0
        else:
            kelly_return = 0.0

        kelly_capital *= (1 + kelly_return)
        kelly_history.append(kelly_capital)
        dispatcher.update(kelly_return > 0)

        random_fraction = random_agent.decide(market_state)
        random_return = random_fraction * market_return
        random_agent.update(random_return)

        state.update("economic_state", {"treasury_balance": {"USDC": kelly_capital}})
        snapshot_cid = ipfs.add_json(state.state)

        await event_bus.publish("economic", {
            "step": step,
            "kelly_capital": kelly_capital,
            "random_capital": random_agent.capital,
            "snapshot_cid": snapshot_cid
        }, source_component="cycle_demo")

        if step % 10 == 0:
            avg_frac = sum(kelly_fractions) / len(kelly_fractions)
            print(f"Шаг {step:3d} | Kelly: {kelly_capital:.2f} | Random: {random_agent.capital:.2f} | avg fraction: {avg_frac:.4f}")

    print("─" * 60)
    print(f"Kelly: {kelly_capital:.2f} | Random: {random_agent.capital:.2f}")
    print("✅ Цикл завершён. Kelly использовал изолированную песочницу для каждой сделки.")

if __name__ == "__main__":
    asyncio.run(main())