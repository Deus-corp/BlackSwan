#!/usr/bin/env python3
"""
Performs a parameter sweep for the multi-agent economic simulation.

Iterates through combinations of 'burn rate' and 'agent failure probability' to evaluate
impact on survival and capital accumulation. Results are aggregated and serialized.
"""

import itertools
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, TypedDict

# Ensure root path is discoverable
ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.multi_agent_sim import MultiAgentSimulation, SimulationConfig

# --- Constants ---
BURN_RATE_VALUES: List[float] = [0.0, 0.1, 0.2, 0.5, 1.0]
FAILURE_PROB_VALUES: List[float] = [0.0, 0.01, 0.05, 0.1]
SEEDS: List[int] = [0, 1, 2]

NUM_AGENTS: int = 6
TOTAL_STEPS: int = 200
SHOCK_PROBABILITY: float = 0.0

OUTPUT_DIR: Path = Path("sim")
SWEEP_OUTPUT_FILENAME: str = "sweep_results.json"

class SimulationMetrics(TypedDict, total=False):
    agents_alive: int
    kelly_avg_capital: float
    random_avg_capital: float
    burn_rate: float
    failure_prob: float
    seed: int

class SummaryEntry(TypedDict):
    burn_rate: float
    failure_prob: float
    avg_alive: float
    avg_kelly: float
    avg_random: float
    kelly_advantage: float

def get_safe_mean(data: List[float]) -> float:
    """Calculate mean of a list, returning 0.0 for empty inputs."""
    return statistics.mean(data) if data else 0.0

def run_sweep() -> None:
    """Main orchestration for the simulation parameter sweep."""
    print("Starting parameter sweep...")

    all_results: List[SimulationMetrics] = []

    for burn_rate, failure_prob, seed in itertools.product(BURN_RATE_VALUES, FAILURE_PROB_VALUES, SEEDS):
        random.seed(seed)
        
        config = SimulationConfig(
            num_agents=NUM_AGENTS,
            steps=TOTAL_STEPS,
            burn_rate_per_step=burn_rate,
            agent_failure_prob=failure_prob,
            shock_probability=SHOCK_PROBABILITY
        )
        sim = MultiAgentSimulation(config)
        
        try:
            metrics: Dict[str, Any] = sim.run()
            run_metrics: SimulationMetrics = {
                "agents_alive": metrics.get("agents_alive", 0),
                "kelly_avg_capital": metrics.get("kelly_avg_capital", 0.0),
                "random_avg_capital": metrics.get("random_avg_capital", 0.0),
                "burn_rate": burn_rate,
                "failure_prob": failure_prob,
                "seed": seed
            }
            all_results.append(run_metrics)
            print(f"  [Success] burn={burn_rate:.2f}, fail={failure_prob:.3f}, seed={seed}")
        except Exception as e:
            print(f"  [Error] burn={burn_rate:.2f}, fail={failure_prob:.3f}, seed={seed}: {e}")

    # Aggregate results
    grouped: Dict[Tuple[float, float], List[SimulationMetrics]] = {}
    for r in all_results:
        grouped.setdefault((r["burn_rate"], r["failure_prob"]), []).append(r)

    summary_list: List[SummaryEntry] = []
    for (br, fp), data in grouped.items():
        avg_alive = get_safe_mean([float(r.get("agents_alive", 0)) for r in data])
        avg_kelly = get_safe_mean([r.get("kelly_avg_capital", 0.0) for r in data])
        avg_rand = get_safe_mean([r.get("random_avg_capital", 0.0) for r in data])
        
        summary_list.append({
            "burn_rate": br,
            "failure_prob": fp,
            "avg_alive": avg_alive,
            "avg_kelly": avg_kelly,
            "avg_random": avg_rand,
            "kelly_advantage": avg_kelly - avg_rand
        })

    # Sort: survival count desc, then advantage desc
    summary_list.sort(key=lambda x: (x["avg_alive"], x["kelly_advantage"]), reverse=True)

    # Save output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / SWEEP_OUTPUT_FILENAME
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "config": {"num_agents": NUM_AGENTS, "steps": TOTAL_STEPS}, 
            "summary": summary_list
        }, f, indent=2)

    print(f"\nSweep complete. Summary saved to {output_path}")

if __name__ == "__main__":
    run_sweep()