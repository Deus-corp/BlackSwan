#!/usr/bin/env python3
"""Evolution experiment for resource-allocation parameters.

This module preserves the legacy Kelly/ROIDispatcher experiment API while making
it explicit that this is an experiment harness, not the core runtime.

Backward-compatible exports used by other modules:
- PARAM_BOUNDS
- random_params()
- evaluate(params, seed=None)
- mutate(params, scale=0.1)
- crossover(p1, p2)
"""

from __future__ import annotations

import copy
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

ROOT: Final[Path] = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.engine.environment import MarketEnvironment
from src.economy.roi_dispatcher import ROIDispatcher


POP_SIZE: Final[int] = 10
GENERATIONS: Final[int] = 10
STEPS: Final[int] = 100
INITIAL_CAPITAL: Final[float] = 1000.0
DRIFT: Final[float] = 0.002
VOLATILITY: Final[float] = 0.01
TRANSACTION_FEE: Final[float] = 1.0
TRADE_RETURN_FACTOR: Final[float] = 0.1

PARAM_BOUNDS: Final[dict[str, tuple[float, float]]] = {
    # Legacy ROI dispatcher knobs.
    "max_risk_per_trade": (0.01, 0.2),
    "phi_llm": (0.05, 0.5),
}


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    """Summary of one evolution run."""

    best_params: dict[str, float]
    best_fitness: float
    average_fitness: float
    generations: int
    population_size: int


def random_params(rng: Optional[random.Random] = None) -> dict[str, float]:
    """Generate parameter set sampled within PARAM_BOUNDS."""
    generator = rng or random
    return {
        key: generator.uniform(low, high)
        for key, (low, high) in PARAM_BOUNDS.items()
    }


def evaluate(params: dict[str, float], seed: Optional[int] = None) -> float:
    """Evaluate resource-allocation parameters in a stochastic environment."""
    rng = random.Random(seed)

    market = MarketEnvironment(
        volatility=VOLATILITY,
        drift=DRIFT,
        initial_price=1.0,
        seed=seed,
    )
    dispatcher = ROIDispatcher(config=_bounded_params(params))
    capital = INITIAL_CAPITAL

    for _ in range(STEPS):
        state = market.step_state()
        market_state = {
            "price": float(state.get("price", 0.0)),
            "volatility_estimate": float(state.get("volatility_estimate", VOLATILITY)),
            "drift": DRIFT,
        }

        fraction, _ = dispatcher.evaluate(market_state, capital)

        if fraction > 0:
            # Keep legacy behavior but add a tiny random term to avoid overfitting
            # completely deterministic drift.
            environmental_noise = rng.uniform(-0.001, 0.001)
            ret = market_state["price"] * fraction * TRADE_RETURN_FACTOR + environmental_noise
            capital = max(0.0, capital * (1.0 + ret) - TRANSACTION_FEE)

        if capital <= 0:
            break

    return float(capital)


def mutate(params: dict[str, float], scale: float = 0.1, rng: Optional[random.Random] = None) -> dict[str, float]:
    """Apply boundary-clamped mutation to parameters."""
    generator = rng or random
    mutation_scale = max(0.0, float(scale))
    mutated = copy.deepcopy(_bounded_params(params))

    for key, (low, high) in PARAM_BOUNDS.items():
        span = high - low
        delta = generator.uniform(-mutation_scale, mutation_scale) * span
        mutated[key] = _clamp(mutated[key] + delta, low, high)

    return mutated


def crossover(
    p1: dict[str, float],
    p2: dict[str, float],
    rng: Optional[random.Random] = None,
) -> dict[str, float]:
    """Uniform crossover between two parameter sets."""
    generator = rng or random
    parent_a = _bounded_params(p1)
    parent_b = _bounded_params(p2)

    return {
        key: parent_a[key] if generator.random() < 0.5 else parent_b[key]
        for key in PARAM_BOUNDS
    }


def run_evolution(
    *,
    pop_size: int = POP_SIZE,
    generations: int = GENERATIONS,
    seed: Optional[int] = None,
) -> EvolutionResult:
    """Run the standalone evolution experiment."""
    if pop_size < 2:
        raise ValueError("pop_size must be >= 2")
    if generations < 1:
        raise ValueError("generations must be >= 1")

    rng = random.Random(seed)
    population = [random_params(rng) for _ in range(pop_size)]

    best_overall: dict[str, float] = {}
    best_fitness = float("-inf")
    last_avg_fitness = 0.0

    for gen in range(generations):
        fitnesses = [
            evaluate(individual, seed=(seed or 0) + gen * 10_000 + index)
            for index, individual in enumerate(population)
        ]

        for index, fitness in enumerate(fitnesses):
            if fitness > best_fitness:
                best_fitness = fitness
                best_overall = copy.deepcopy(population[index])

        last_avg_fitness = statistics.fmean(fitnesses)
        sorted_indices = sorted(range(pop_size), key=lambda idx: fitnesses[idx], reverse=True)

        elite_count = max(1, min(2, pop_size // 3))
        new_population = [copy.deepcopy(population[index]) for index in sorted_indices[:elite_count]]

        while len(new_population) < pop_size:
            parent_a = population[sorted_indices[0]]
            parent_b = population[rng.choice(sorted_indices[: max(2, pop_size // 2)])]
            child = crossover(parent_a, parent_b, rng)

            if rng.random() < 0.35:
                child = mutate(child, rng=rng)

            new_population.append(child)

        population = new_population

    return EvolutionResult(
        best_params=best_overall,
        best_fitness=best_fitness,
        average_fitness=last_avg_fitness,
        generations=generations,
        population_size=pop_size,
    )


def main() -> None:
    """CLI entrypoint for the experiment."""
    print("=== Starting Resource Allocation Evolution ===\n")

    population = [random_params() for _ in range(POP_SIZE)]
    best_overall: dict[str, float] = {}
    best_fitness = float("-inf")

    for gen in range(GENERATIONS):
        fitnesses = [evaluate(individual, seed=gen * 100 + index) for index, individual in enumerate(population)]

        for index, fitness in enumerate(fitnesses):
            if fitness > best_fitness:
                best_fitness = fitness
                best_overall = copy.deepcopy(population[index])

        avg_fit = statistics.fmean(fitnesses)
        print(f"Generation {gen + 1}: Avg={avg_fit:.2f}, Max={max(fitnesses):.2f}")

        sorted_indices = sorted(range(POP_SIZE), key=lambda index: fitnesses[index], reverse=True)
        new_population = [copy.deepcopy(population[sorted_indices[0]])]

        while len(new_population) < POP_SIZE:
            parent_a = population[sorted_indices[0]]
            parent_b = population[random.randrange(POP_SIZE)] if random.random() < 0.3 else parent_a
            child = crossover(parent_a, parent_b)

            if random.random() < 0.3:
                child = mutate(child)

            new_population.append(child)

        population = new_population

    print(f"\n=== Best Parameters Found ===\n{best_overall}")
    print(f"Final Resources: {best_fitness:.2f}")


def _bounded_params(params: dict[str, float]) -> dict[str, float]:
    bounded: dict[str, float] = {}

    for key, (low, high) in PARAM_BOUNDS.items():
        bounded[key] = _clamp(_safe_float(params.get(key), (low + high) / 2.0), low, high)

    return bounded


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and number not in (float("inf"), float("-inf")) else default


if __name__ == "__main__":
    main()