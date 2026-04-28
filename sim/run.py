import argparse
import yaml
from engine.environment import MarketEnvironment
from engine.agents import KellyAgent, RandomAgent
from engine.metrics import compute_metrics, plot_results

def main():
    parser = argparse.ArgumentParser(description="Swarm-Sim economic simulator")
    parser.add_argument("--config", default="scenarios/basic_economic.yaml", help="Path to YAML config")
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    sim_cfg = config["simulation"]
    market_cfg = config["market"]
    agents_cfg = config["agents"]

    # Инициализация рынка
    market = MarketEnvironment(volatility=market_cfg["volatility"], drift=market_cfg.get("drift", 0.0))

    # Инициализация агентов
    agents = []
    for ac in agents_cfg:
        if ac["type"] == "KellyAgent":
            agents.append(KellyAgent(capital=ac["capital"], max_risk=ac.get("max_risk", 0.02), phi=ac.get("phi", 0.25)))
        elif ac["type"] == "RandomAgent":
            agents.append(RandomAgent(capital=ac["capital"], max_risk=ac.get("max_risk", 0.02)))
        else:
            raise ValueError(f"Unknown agent type: {ac['type']}")

    # Симуляция
    for step in range(sim_cfg["steps"]):
        market_state = market.get_state()
        # Решение агентов и инвестиции
        for agent in agents:
            fraction = agent.decide(market_state)
            # Доходность агента: fraction * (изменение цены)
            price_before = market.prices[-1]
            new_price = market.step()  # двигаем рынок один раз за всех
            market_return = (new_price - price_before) / price_before
            agent_return = fraction * market_return
            agent.update(agent_return)

    # Сбор метрик и отображение
    agents_data = {}
    for agent in agents:
        name = type(agent).__name__
        metrics = compute_metrics(agent.history)
        print(f"\n{name}:")
        for k, v in metrics.items():
            print(f"  {k}: {v:.4f}")
        agents_data[name] = (agent.history, agent)

    # Добавляем market для возможности отображения цены
    for agent in agents:
        agent.market = market
    plot_results(agents_data)

if __name__ == "__main__":
    main()