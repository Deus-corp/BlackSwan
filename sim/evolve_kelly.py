#!/usr/bin/env python3
"""
Ouroboros Prototype: Evolution of ROIDispatcher (Kelly) parameters.

This script executes a genetic algorithm to optimize trading parameters 
for the ROIDispatcher, maximizing profitability via market simulation.
"""
import sys
import random
import copy
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Final, Union, Optional

# Configure sys.path to resolve project root
ROOT: Final[Path] = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.engine.environment import MarketEnvironment
from src.economy.roi_dispatcher import ROIDispatcher

# --- Configuration Parameters ---
POP_SIZE: Final[int] = 10
GENERATIONS: Final[int] = 10
STEPS: Final[int] = 100
INITIAL_CAPITAL: Final[float] = 1000.0
DRIFT: Final[float] = 0.002
VOLATILITY: Final[float] = 0.01
TRANSACTION_FEE: Final[float] = 1.0
TRADE_RETURN_FACTOR: Final[float] = 0.1

PARAM_BOUNDS: Final[Dict[str, Tuple[float, float]]] = {
    "max_risk_per_trade": (0.01, 0.2),
    "phi_llm": (0.05, 0.5)
}

def random_params() -> Dict[str, float]:
    """Generates a parameter set sampled within defined boundaries."""
    return {
        "max_risk_per_trade": random.uniform(*PARAM_BOUNDS["max_risk_per_trade"]),
        "phi_llm": random.uniform(*PARAM_BOUNDS["phi_llm"])
    }

def evaluate(params: Dict[str, float], seed: Optional[int] = None) -> float:
    """Simulates market conditions and returns final capital (fitness)."""
    if seed is not None:
        random.seed(seed)
    
    market: MarketEnvironment = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)
    dispatcher: ROIDispatcher = ROIDispatcher(config=params)
    capital: float = INITIAL_CAPITAL

    for _ in range(STEPS):
        raw_state = market.step()
        market_state: Dict[str, float] = {
            "price": raw_state.get("price", 0.0) if isinstance(raw_state, dict) else float(raw_state),
            "volatility_estimate": VOLATILITY,
            "drift": DRIFT
        }
        
        fraction, _ = dispatcher.evaluate(market_state, capital)
        
        if fraction > 0:
            ret: float = market_state["price"] * fraction * TRADE_RETURN_FACTOR
            capital = max(0.0, capital * (1 + ret) - TRANSACTION_FEE)
        
        if capital <= 0:
            break
    return capital

def mutate(params: Dict[str, float], scale: float = 0.1) -> Dict[str, float]:
    """Applies boundary-clamped Gaussian mutation to parameters."""
    mutated: Dict[str, float] = copy.deepcopy(params)
    for key, (low, high) in PARAM_BOUNDS.items():
        delta = random.uniform(-scale, scale) * (high - low)
        mutated[key] = max(low, min(high, mutated[key] + delta))
    return mutated

def crossover(p1: Dict[str, float], p2: Dict[str, float]) -> Dict[str, float]:
    """Performs uniform crossover between two sets of parameters."""
    return {k: (p1[k] if random.random() < 0.5 else p2[k]) for k in PARAM_BOUNDS}

def main() -> None:
    """Genetic Algorithm execution loop."""
    print("=== Starting Kelly Strategy Evolution ===\n")
    population: List[Dict[str, float]] = [random_params() for _ in range(POP_SIZE)]
    best_overall: Dict[str, float] = {}
    best_fitness: float = -1.0

    for gen in range(GENERATIONS):
        fitnesses: List[float] = [evaluate(ind, seed=gen * 100 + i) for i, ind in enumerate(population)]
        
        # Track best
        for i, fit in enumerate(fitnesses):
            if fit > best_fitness:
                best_fitness = fit
                best_overall = copy.deepcopy(population[i])

        avg_fit = statistics.mean(fitnesses)
        print(f"Generation {gen+1}: Avg={avg_fit:.2f}, Max={max(fitnesses):.2f}")

        # Selection & New Population Generation
        sorted_indices = sorted(range(POP_SIZE), key=lambda i: fitnesses[i], reverse=True)
        new_pop: List[Dict[str, float]] = [population[sorted_indices[0]]]
        
        while len(new_pop) < POP_SIZE:
            parent_a = population[sorted_indices[0]]
            parent_b = population[random.randrange(POP_SIZE)] if random.random() < 0.3 else population[sorted_indices[0]]
            child = crossover(parent_a, parent_b)
            if random.random() < 0.3:
                child = mutate(child)
            new_pop.append(child)
        population = new_pop

    print(f"\n=== Best Parameters Found ===\n{best_overall}")
    print(f"Final Capital: {best_fitness:.2f}")

if __name__ == "__main__":
    main()