#!/usr/bin/env python3
"""
Performs a parameter sweep for the multi-agent economic simulation.

This script iterates through different combinations of 'burn rate' and 'agent failure probability'
to evaluate their impact on simulation outcomes, such as agent survival and capital accumulation.
Results are grouped, averaged, and saved to a JSON file.
"""

import sys
import os
import itertools
import json
import statistics
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple, TypedDict, Union

# Set up the system path to allow importing modules from the parent directory.
# This ensures that `sim.multi_agent_sim` can be found.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import necessary classes from the simulation module.
from sim.multi_agent_sim import SimulationConfig, MultiAgentSimulation

# --- Configuration Constants for the Sweep ---
BURN_RATE_VALUES: List[float] = [0.0, 0.1, 0.2, 0.5, 1.0]
FAILURE_PROB_VALUES: List[float] = [0.0, 0.01, 0.05, 0.1]
SEEDS: List[int] = list(range(3))  # Number of repetitions for each parameter combination

# Fixed simulation parameters for each run within this sweep.
NUM_AGENTS: int = 6
TOTAL_STEPS: int = 200
SHOCK_PROBABILITY: float = 0.0 # Keeping shock probability constant for this sweep

# Output file settings.
OUTPUT_DIR: Path = Path("sim")
SWEEP_OUTPUT_FILENAME: str = "sweep_results.json"

# --- Type Definitions for clarity and maintainability ---
class SimulationMetrics(TypedDict, total=False):
    """
    Defines the structure of metrics expected from a single simulation run.
    `total=False` allows for flexibility if certain metrics are conditionally present.
    """
    agents_alive: int
    kelly_avg_capital: float
    random_avg_capital: float
    burn_rate: float
    failure_prob: float
    seed: int
    # Additional metrics can be added here as needed


class SummaryEntry(TypedDict):
    """
    Defines the structure for each entry in the summarized sweep results.
    """
    burn_rate: float
    failure_prob: float
    avg_alive: float
    avg_kelly: float
    avg_random: float
    kelly_advantage: float


class SweepResultsOutput(TypedDict):
    """
    Defines the overall structure for the JSON output file containing all sweep data.
    """
    config: Dict[str, Any]
    raw_results: List[SimulationMetrics]
    summary: List[SummaryEntry]

# --- Helper Function ---
def safe_mean(data: List[float]) -> float:
    """
    Calculates the mean of a list of floats.
    Returns 0.0 for an empty list to prevent statistics.mean() from raising an error.
    """
    return statistics.mean(data) if data else 0.0


def main() -> None:
    """
    Main function to perform the parameter sweep for the multi-agent economic simulation.
    It iterates through different combinations of 'burn rate' and 'agent failure probability',
    runs simulations, collects metrics, and saves a summarized report to a JSON file.
    """
    print("Starting parameter sweep...")

    all_results: List[SimulationMetrics] = []

    # Iterate over all combinations of defined parameters.
    for burn_rate, failure_prob, seed in itertools.product(BURN_RATE_VALUES, FAILURE_PROB_VALUES, SEEDS):
        random.seed(seed)  # Set seed for reproducibility for each specific run.
        
        # Configure the simulation for the current parameter set.
        config = SimulationConfig(
            num_agents=NUM_AGENTS,
            steps=TOTAL_STEPS,
            burn_rate_per_step=burn_rate,
            agent_failure_prob=failure_prob,
            shock_probability=SHOCK_PROBABILITY
        )
        sim = MultiAgentSimulation(config)
        
        try:
            metrics: Dict[str, Any] = sim.run()  # Run the simulation and collect metrics.
        except Exception as e:
            # Catch any exceptions during a simulation run to prevent the entire sweep from crashing.
            print(f"  Error running sim for burn={burn_rate:.2f}, fail={failure_prob:.3f}, seed={seed}: {e}")
            continue # Skip this specific combination and proceed to the next.

        # Combine sweep parameters with simulation output metrics.
        run_metrics: SimulationMetrics = {
            "burn_rate": burn_rate,
            "failure_prob": failure_prob,
            "seed": seed,
            **metrics # Merge dictionary containing simulation output.
        }
        all_results.append(run_metrics)
        
        # Provide real-time feedback on simulation progress.
        # Use .get() with a default value to prevent KeyError if a metric is unexpectedly missing.
        print(f"  Ran sim: burn={burn_rate:.2f}, fail={failure_prob:.3f}, seed={seed}. Agents alive: {run_metrics.get('agents_alive', 'N/A')}")

    # Group raw results by burn rate and failure probability for aggregation.
    grouped_results: Dict[Tuple[float, float], List[SimulationMetrics]] = {}
    for r in all_results:
        key: Tuple[float, float] = (r["burn_rate"], r["failure_prob"])
        grouped_results.setdefault(key, []).append(r)

    summary_list: List[SummaryEntry] = []
    for (burn_rate, failure_prob), run_data_list in grouped_results.items():
        # Extract individual metric values for averaging, filtering out any missing keys.
        alive_counts = [r["agents_alive"] for r in run_data_list if "agents_alive" in r]
        kelly_capitals = [r["kelly_avg_capital"] for r in run_data_list if "kelly_avg_capital" in r]
        random_capitals = [r["random_avg_capital"] for r in run_data_list if "random_avg_capital" in r]

        # Calculate average metrics for each group using the `safe_mean` helper function.
        avg_alive: float = safe_mean(list(map(float, alive_counts))) # Cast to float for mean consistency
        avg_kelly: float = safe_mean(kelly_capitals)
        avg_random: float = safe_mean(random_capitals)
        
        summary_list.append(SummaryEntry(
            burn_rate=burn_rate,
            failure_prob=failure_prob,
            avg_alive=avg_alive,
            avg_kelly=avg_kelly,
            avg_random=avg_random,
            kelly_advantage=avg_kelly - avg_random  # Calculate Kelly's strategy advantage.
        ))

    # Sort the summary list: first by average agents alive (descending), then by Kelly's advantage (descending).
    summary_list.sort(key=lambda x: (x["avg_alive"], x["kelly_advantage"]), reverse=True)

    print("\nParameter sweep summary (best survival first):")
    for s in summary_list:
        print(f"burn={s['burn_rate']:.2f}, fail={s['failure_prob']:.3f}: alive={s['avg_alive']:.1f}, Kelly={s['avg_kelly']:.1f}, Random={s['avg_random']:.1f}, advantage={s['kelly_advantage']:.1f}")

    # Prepare the final output data structure for JSON serialization.
    output_data: SweepResultsOutput = {
        "config": {
            "num_agents": NUM_AGENTS,
            "steps": TOTAL_STEPS,
            "burn_rate_values": BURN_RATE_VALUES,
            "failure_prob_values": FAILURE_PROB_VALUES,
            "seeds": SEEDS,
            "shock_probability": SHOCK_PROBABILITY
        },
        "raw_results": all_results,
        "summary": summary_list
    }
    
    # Ensure the output directory exists before saving the file.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path: Path = OUTPUT_DIR / SWEEP_OUTPUT_FILENAME

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2) # Use indent for readable JSON output.

    print(f"\nSweep results saved to {output_path}")

if __name__ == "__main__":
    main()