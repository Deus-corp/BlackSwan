def test_cognition_imports() -> None:
    from src.cognition import CuriosityEngine, MetaPOMDPAgent, SurvivalEvaluator

    assert CuriosityEngine is not None
    assert MetaPOMDPAgent is not None
    assert SurvivalEvaluator is not None


def test_evolution_imports() -> None:
    from src.evolution import GeneticEngine, Genome

    engine = GeneticEngine(pop_size=4)
    engine.initialize()

    assert Genome is not None
    assert engine.population


def test_simulation_imports() -> None:
    from src.simulation import KellyAgent, MarketEnvironment, RandomAgent, compute_metrics

    env = MarketEnvironment(seed=1)
    first = env.step()
    second = env.step()

    assert first > 0
    assert second > 0

    kelly = KellyAgent(capital=1000.0)
    random_agent = RandomAgent(capital=1000.0, seed=1)

    assert kelly.capital == 1000.0
    assert random_agent.capital == 1000.0

    metrics = compute_metrics([1000.0, 1001.0, 1002.0])
    assert metrics["final_capital"] == 1002.0