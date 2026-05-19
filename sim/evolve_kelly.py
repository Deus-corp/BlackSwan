#!/usr/bin/env python3
"""
Ouroboros Prototype: Evolution of ROIDispatcher (Kelly) parameters.

This script demonstrates that a genetic algorithm can be used to evolve
and improve the profitability of trading strategies (specifically,
the parameters for the ROIDispatcher, which implements Kelly criterion-like
logic) compared to randomly initialized strategies.

It defines the evolutionary process including evaluation, mutation,
and crossover, and tracks the best performing strategy over generations.
"""
import sys
import random
import copy
import statistics
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Final, Union

# Adjust Python path to import modules from the project root
ROOT: Final[Path] = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.engine.environment import MarketEnvironment
from src.economy.roi_dispatcher import ROIDispatcher

# --- Configuration for the Genetic Algorithm ---
POP_SIZE: Final[int] = 10
GENERATIONS: Final[int] = 10
STEPS: Final[int] = 100              # Simulation steps to evaluate a single individual
INITIAL_CAPITAL: Final[float] = 1000.0
DRIFT: Final[float] = 0.002
VOLATILITY: Final[float] = 0.01
TRANSACTION_FEE: Final[float] = 1.0  # Fixed fee deducted per successful trade
TRADE_RETURN_FACTOR: Final[float] = 0.1 # Multiplier for calculating actual return from price movement and fraction

# Bounds for strategy parameters, used for initialization and mutation
PARAM_BOUNDS: Final[Dict[str, Tuple[float, float]]] = {
    "max_risk_per_trade": (0.01, 0.2),
    "phi_llm": (0.05, 0.5)
}

def random_params() -> Dict[str, float]:
    """
    Generates a dictionary of strategy parameters with random values within their defined bounds.

    Returns:
        Dict[str, float]: A dictionary of randomized strategy parameters.
    """
    return {
        "max_risk_per_trade": random.uniform(*PARAM_BOUNDS["max_risk_per_trade"]),
        "phi_llm": random.uniform(*PARAM_BOUNDS["phi_llm"])
    }

def evaluate(params: Dict[str, float], seed: Optional[int] = None) -> float:
    """
    Evaluates a set of strategy parameters by running a market simulation.

    Args:
        params (Dict[str, float]): The strategy parameters to evaluate.
        seed (Optional[int]): Seed for the random number generator to ensure reproducible
                              market simulations for a given set of parameters. If None,
                              the global random state is used.

    Returns:
        float: The final capital after the simulation, representing the fitness of the parameters.
    """
    if seed is not None:
        random.seed(seed)
    
    market: MarketEnvironment = MarketEnvironment(volatility=VOLATILITY, drift=DRIFT)
    dispatcher: ROIDispatcher = ROIDispatcher(config=params)
    capital: float = INITIAL_CAPITAL

    for _ in range(STEPS):
        raw_state_output: Union[float, Dict[str, float]] = market.step()
        
        market_state: Dict[str, float]
        if isinstance(raw_state_output, dict):
            market_state = raw_state_output
        else:
            # Handle cases where MarketEnvironment.step() might return a simple price float
            # instead of a full dictionary state. This provides backward compatibility.
            market_state = {
                "price": raw_state_output,
                "volatility_estimate": VOLATILITY, # Default if not in dict
                "drift": DRIFT                     # Default if not in dict
            }
        
        # Ensure required keys are present for ROIDispatcher, providing defaults if missing.
        # This adds robustness if the market environment doesn't always provide all keys.
        if "price" not in market_state:
            market_state["price"] = 0.0
        if "volatility_estimate" not in market_state:
            market_state["volatility_estimate"] = VOLATILITY
        if "drift" not in market_state:
            market_state["drift"] = DRIFT

        fraction, _ = dispatcher.evaluate(market_state, capital)
        
        if fraction > 0: # A trade is proposed
            # Calculate return based on market price movement, fraction invested, and a return factor
            # For simplicity, assuming 'fraction' is the proportion of capital to be risked.
            ret: float = market_state["price"] * fraction * TRADE_RETURN_FACTOR
            capital *= (1 + ret)
            capital -= TRANSACTION_FEE   # Deduct fixed commission per trade
        
        if capital <= 0:
            capital = 0.0 # Ensure capital doesn't go negative and breaks simulation
            break
    return capital

def mutate(params: Dict[str, float], scale: float = 0.1) -> Dict[str, float]:
    """
    Applies a random mutation to the given parameters, keeping them within their defined bounds.

    Args:
        params (Dict[str, float]): The parameters dictionary to mutate.
        scale (float): The maximum proportion of the parameter's total range that
                       can be added or subtracted during mutation.

    Returns:
        Dict[str, float]: A new dictionary of mutated parameters.
    """
    new_params: Dict[str, float] = copy.deepcopy(params)
    for k, (min_bound, max_bound) in PARAM_BOUNDS.items():
        # Calculate delta as a proportion of the parameter's total range
        delta: float = random.uniform(-scale, scale) * (max_bound - min_bound)
        new_params[k] += delta
        # Clamp the new value within its defined bounds
        new_params[k] = max(min_bound, min(max_bound, new_params[k]))
    return new_params

def crossover(p1: Dict[str, float], p2: Dict[str, float]) -> Dict[str, float]:
    """
    Performs uniform crossover between two parent parameter sets.

    For each parameter, it randomly selects the value from either parent with 50% probability.

    Args:
        p1 (Dict[str, float]): Parameters of the first parent.
        p2 (Dict[str, float]): Parameters of the second parent.

    Returns:
        Dict[str, float]: A new dictionary representing the child's parameters.
    """
    child: Dict[str, float] = {}
    for k in PARAM_BOUNDS: # Iterate over keys to ensure all parameters are included in the child
        child[k] = p1[k] if random.random() < 0.5 else p2[k]
    return child

# --- Genetic Algorithm Main Loop ---
population: List[Dict[str, float]] = [random_params() for _ in range(POP_SIZE)]
best_overall: Optional[Dict[str, float]] = None
best_fitness: float = 0.0

print("=== Запуск эволюции стратегии Kelly ===\n")
for gen in range(GENERATIONS):
    # Evaluate all individuals in the current population
    fitnesses: List[float] = []
    for params in population:
        # All individuals within a generation are evaluated under the same market conditions (same seed),
        # allowing for fair comparison within the generation. The seed changes each generation for diversity.
        fit: float = evaluate(params, seed=gen * 100)
        fitnesses.append(fit)
        
        # Update overall best individual found so far
        if fit > best_fitness:
            best_fitness = fit
            best_overall = copy.deepcopy(params)

    # Log generation statistics
    avg_fit: float = statistics.mean(fitnesses)
    max_fit: float = max(fitnesses)
    print(f"Поколение {gen+1}: средний капитал = {avg_fit:.2f}, максимальный = {max_fit:.2f}")

    # Selection (elitism + tournament)
    # Sort indices based on fitness in descending order to identify the elite
    sorted_indices: List[int] = sorted(range(POP_SIZE), key=lambda i: fitnesses[i], reverse=True)
    
    # Elitism: carry over the best individual directly to the next generation
    new_pop: List[Dict[str, float]] = [population[sorted_indices[0]]]
    
    # Fill the rest of the new population through selection, crossover, and mutation
    while len(new_pop) < POP_SIZE:
        # Tournament selection: pick two random individuals and select the fitter one as primary parent
        i1: int = random.randrange(POP_SIZE)
        i2: int = random.randrange(POP_SIZE)
        # Ensure i1 and i2 are distinct for tournament selection
        while i2 == i1:
            i2 = random.randrange(POP_SIZE)

        winner_idx: int = i1 if fitnesses[i1] > fitnesses[i2] else i2
        winner_params: Dict[str, float] = population[winner_idx]

        # Crossover strategy: either with the elite individual or another tournament winner
        parent2: Dict[str, float]
        if random.random() < 0.7: # 70% chance to crossover with the best individual of the generation (elite)
            parent2 = population[sorted_indices[0]]
        else:
            # Otherwise, perform crossover with another individual chosen via tournament selection
            # To ensure parent2 is distinct from winner_params, another tournament could be run.
            # Here, for simplicity and adherence to implied original intent, a potentially same winner is allowed.
            parent2 = winner_params

        child: Dict[str, float] = crossover(winner_params, parent2)
        
        # Mutation: apply mutation with a certain probability
        if random.random() < 0.3: # 30% chance for mutation
            child = mutate(child, scale=0.1) # Mutation scale
        
        new_pop.append(child)
    
    population = new_pop # Replace old population with the new, evolved one

print(f"\n=== Лучшие параметры после {GENERATIONS} поколений ===")
if best_overall is not None:
    print(f"max_risk_per_trade = {best_overall['max_risk_per_trade']:.4f}")
    print(f"phi_llm = {best_overall['phi_llm']:.4f}")
    print(f"Достигнутый капитал = {best_fitness:.2f}")
else:
    print("No best parameters found (possible if GENERATIONS is 0 or all fitnesses were 0).")

# Comparison with standard parameters from documentation
standard_params: Dict[str, float] = {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
# Evaluate standard parameters with a distinct seed to ensure a fair, independent comparison
standard_fitness: float = evaluate(standard_params, seed=999)
print(f"\nКапитал со стандартными параметрами (0.05, 0.15): {standard_fitness:.2f}")

# Calculate and print improvement
if best_overall is not None:
    improvement: float = best_fitness - standard_fitness
    print(f"Улучшение: {improvement:.2f}")
else:
    print("Cannot calculate improvement as no best parameters were found.")
