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
from typing import List, Dict, Any, Tuple, Union

# Set up the system path to allow importing modules from the parent directory
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Assuming these classes are defined in sim.multi_agent_sim
from sim.multi_agent_sim import SimulationConfig, MultiAgentSimulation

# Define parameter ranges for the sweep
burn_values: List[float] = [0.0, 0.1, 0.2, 0.5, 1.0]
failure_values: List[float] = [0.0, 0.01, 0.05, 0.1]
seeds: List[int] = list(range(3))  # 3 repetitions for each parameter combination

results: List[Dict[str, Any]] = []

print("Starting parameter sweep...")
# Iterate over all combinations of parameters
for burn, fail, seed in itertools.product(burn_values, failure_values, seeds):
    random.seed(seed)  # Set seed for reproducibility for each run
    
    # Configure and run the simulation
    config = SimulationConfig(
        num_agents=6,
        steps=200,
        burn_rate_per_step=burn,
        agent_failure_prob=fail,
        shock_probability=0.0  # Keeping shock probability constant for this sweep
    )
    sim = MultiAgentSimulation(config)
    metrics: Dict[str, Any] = sim.run()  # Assuming sim.run() returns a dict of metrics
    
    # Add sweep parameters to the metrics for later grouping
    metrics.update({"burn_rate": burn, "failure_prob": fail, "seed": seed})
    results.append(metrics)
    # Using .get() with a default value to prevent KeyError if key is missing
    print(f"  Ran sim: burn={burn:.2f}, fail={fail:.3f}, seed={seed}. Agents alive: {metrics.get('agents_alive', 'N/A')}")

# Group results by burn rate and failure probability, then average
grouped: Dict[Tuple[float, float], List[Dict[str, Any]]] = {}
for r in results:
    key: Tuple[float, float] = (r["burn_rate"], r["failure_prob"])
    grouped.setdefault(key, []).append(r)

summary: List[Dict[str, Any]] = []
for (burn, fail), lst in grouped.items():
    # Calculate average metrics for each group
    # Using a list comprehension with checks for empty iterables to avoid errors
    avg_alive: float = statistics.mean(r["agents_alive"] for r in lst if "agents_alive" in r) if lst else 0.0
    avg_kelly: float = statistics.mean(r["kelly_avg_capital"] for r in lst if "kelly_avg_capital" in r) if lst else 0.0
    avg_random: float = statistics.mean(r["random_avg_capital"] for r in lst if "random_avg_capital" in r) if lst else 0.0
    
    summary.append({
        "burn_rate": burn,
        "failure_prob": fail,
        "avg_alive": avg_alive,
        "avg_kelly": avg_kelly,
        "avg_random": avg_random,
        "kelly_advantage": avg_kelly - avg_random  # Calculate Kelly's advantage
    })

# Sort the summary by average agents alive and then by Kelly's advantage
summary.sort(key=lambda x: (x["avg_alive"], x["kelly_advantage"]), reverse=True)

print("\nParameter sweep summary (best survival first):")
for s in summary:
    print(f"burn={s['burn_rate']:.2f}, fail={s['failure_prob']:.3f}: alive={s['avg_alive']:.1f}, Kelly={s['avg_kelly']:.1f}, Random={s['avg_random']:.1f}, advantage={s['kelly_advantage']:.1f}")

# Save all results to a JSON file
output_data: Dict[str, Any] = {
    "config": {"steps": 200, "agents": 6},  # Fixed simulation parameters for this sweep
    "raw_results": results,
    "summary": summary
}
# Ensure the output directory exists
output_dir: Path = Path("sim")
output_dir.mkdir(parents=True, exist_ok=True)
output_path: Path = output_dir / "sweep_results.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"\nSweep results saved to {output_path}")