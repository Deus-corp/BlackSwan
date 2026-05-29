from src.evolution import Genome
from src.swarms.trade.node_core.evolution import (
    current_volatility,
    dict_to_genome,
    make_genome,
    node_niche,
    population_diversity,
    population_niche_counts,
    recombine,
)


class DummyNode:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.current_params = {
            "max_risk_per_trade": 0.09,
            "phi_llm": 0.5,
            "volatility_threshold": 0.03,
        }
        self.generation = 2
        self.population = [
            Genome(params={"a": 1.0}, fitness=0.1, age=1, niche="exploration"),
            Genome(params={"a": 2.0}, fitness=0.2, age=1, niche="preservation"),
        ]


def test_node_niche_detects_exploration() -> None:
    node = DummyNode()

    assert node_niche(node) == "exploration"


def test_make_genome_returns_serializable_dict() -> None:
    node = DummyNode()

    genome = make_genome(node, {"x": 1.0}, 0.5)

    assert genome["node_id"] == "trade-1"
    assert genome["params"] == {"x": 1.0}
    assert genome["fitness"] == 0.5
    assert genome["generation"] == 2


def test_dict_to_genome_builds_genome() -> None:
    node = DummyNode()

    genome = dict_to_genome(node, {"params": {"x": 1.0}, "fitness": 0.5, "generation": 3})

    assert isinstance(genome, Genome)
    assert genome.params == {"x": 1.0}
    assert genome.fitness == 0.5
    assert genome.age == 3


def test_population_helpers() -> None:
    node = DummyNode()

    assert population_diversity(node) > 0
    assert population_niche_counts(node) == {
        "exploration": 1,
        "preservation": 1,
    }


def test_current_volatility_reads_params() -> None:
    node = DummyNode()

    assert current_volatility(node) == 0.03


def test_recombine_averages_numeric_values() -> None:
    node = DummyNode()

    child = recombine(node, {"x": 1.0, "mode": "a"}, {"x": 3.0, "mode": "b"})

    assert child["x"] == 2.0
    assert child["mode"] in {"a", "b"}