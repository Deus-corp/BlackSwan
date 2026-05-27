#!/usr/bin/env python3
"""Parameter sweep runner for BlackSwan multi-agent simulations.

This is an experiment utility. It explores how environmental stress parameters
affect survival and resource accumulation across multiple stochastic seeds.

Legacy behavior is preserved:
- run_sweep()
- writes sim/sweep_results.json by default
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, TypedDict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.multi_agent_sim import MultiAgentSimulation, SimulationConfig


BURN_RATE_VALUES: list[float] = [0.0, 0.1, 0.2, 0.5, 1.0]
FAILURE_PROB_VALUES: list[float] = [0.0, 0.01, 0.05, 0.1]
SEEDS: list[int] = [0, 1, 2]

NUM_AGENTS = 6
TOTAL_STEPS = 200
SHOCK_PROBABILITY = 0.0

OUTPUT_DIR = Path("sim")
SWEEP_OUTPUT_FILENAME = "sweep_results.json"


class SimulationMetrics(TypedDict, total=False):
    agents_alive: float
    survival_rate: float
    kelly_avg_capital: float
    random_avg_capital: float
    total_capital: float
    total_return: float
    total_trades: float
    burn_rate: float
    failure_prob: float
    seed: int


class SummaryEntry(TypedDict):
    burn_rate: float
    failure_prob: float
    avg_alive: float
    avg_survival_rate: float
    avg_kelly: float
    avg_random: float
    avg_total_capital: float
    avg_total_return: float
    kelly_advantage: float
    runs: int


@dataclass(frozen=True, slots=True)
class SweepConfig:
    """Configuration for a parameter sweep."""

    burn_rates: tuple[float, ...] = tuple(BURN_RATE_VALUES)
    failure_probs: tuple[float, ...] = tuple(FAILURE_PROB_VALUES)
    seeds: tuple[int, ...] = tuple(SEEDS)
    num_agents: int = NUM_AGENTS
    steps: int = TOTAL_STEPS
    shock_probability: float = SHOCK_PROBABILITY
    output_path: Path = OUTPUT_DIR / SWEEP_OUTPUT_FILENAME


def get_safe_mean(data: Iterable[float]) -> float:
    """Return mean of finite values, or 0.0 for empty inputs."""
    values = [float(item) for item in data if _is_finite(item)]
    return statistics.fmean(values) if values else 0.0


def run_sweep(config: SweepConfig | None = None) -> list[SummaryEntry]:
    """Run simulation sweep and write JSON summary."""
    sweep_config = config or SweepConfig()
    print("Starting parameter sweep...")

    all_results: list[SimulationMetrics] = []

    for burn_rate, failure_prob, seed in itertools.product(
        sweep_config.burn_rates,
        sweep_config.failure_probs,
        sweep_config.seeds,
    ):
        sim_config = SimulationConfig(
            num_agents=sweep_config.num_agents,
            steps=sweep_config.steps,
            burn_rate_per_step=burn_rate,
            agent_failure_prob=failure_prob,
            shock_probability=sweep_config.shock_probability,
            seed=seed,
        )
        simulation = MultiAgentSimulation(sim_config)

        try:
            metrics = simulation.run()
            run_metrics: SimulationMetrics = {
                "agents_alive": float(metrics.get("agents_alive", 0.0)),
                "survival_rate": float(metrics.get("survival_rate", 0.0)),
                "kelly_avg_capital": float(metrics.get("kelly_avg_capital", 0.0)),
                "random_avg_capital": float(metrics.get("random_avg_capital", 0.0)),
                "total_capital": float(metrics.get("total_capital", 0.0)),
                "total_return": float(metrics.get("total_return", 0.0)),
                "total_trades": float(metrics.get("total_trades", 0.0)),
                "burn_rate": float(burn_rate),
                "failure_prob": float(failure_prob),
                "seed": int(seed),
            }
            all_results.append(run_metrics)
            print(f"  [Success] burn={burn_rate:.2f}, fail={failure_prob:.3f}, seed={seed}")

        except Exception as exc:
            print(f"  [Error] burn={burn_rate:.2f}, fail={failure_prob:.3f}, seed={seed}: {exc}")

    summary = summarize_results(all_results)
    write_results(sweep_config, all_results, summary)
    print(f"\nSweep complete. Summary saved to {sweep_config.output_path}")
    return summary


def summarize_results(all_results: list[SimulationMetrics]) -> list[SummaryEntry]:
    """Aggregate raw run results by burn/failure pair."""
    grouped: dict[tuple[float, float], list[SimulationMetrics]] = {}

    for result in all_results:
        grouped.setdefault((float(result["burn_rate"]), float(result["failure_prob"])), []).append(result)

    summary: list[SummaryEntry] = []

    for (burn_rate, failure_prob), data in grouped.items():
        avg_alive = get_safe_mean(float(row.get("agents_alive", 0.0)) for row in data)
        avg_survival_rate = get_safe_mean(float(row.get("survival_rate", 0.0)) for row in data)
        avg_kelly = get_safe_mean(float(row.get("kelly_avg_capital", 0.0)) for row in data)
        avg_random = get_safe_mean(float(row.get("random_avg_capital", 0.0)) for row in data)
        avg_total_capital = get_safe_mean(float(row.get("total_capital", 0.0)) for row in data)
        avg_total_return = get_safe_mean(float(row.get("total_return", 0.0)) for row in data)

        summary.append(
            {
                "burn_rate": burn_rate,
                "failure_prob": failure_prob,
                "avg_alive": avg_alive,
                "avg_survival_rate": avg_survival_rate,
                "avg_kelly": avg_kelly,
                "avg_random": avg_random,
                "avg_total_capital": avg_total_capital,
                "avg_total_return": avg_total_return,
                "kelly_advantage": avg_kelly - avg_random,
                "runs": len(data),
            }
        )

    summary.sort(
        key=lambda item: (
            item["avg_survival_rate"],
            item["avg_total_return"],
            item["kelly_advantage"],
        ),
        reverse=True,
    )
    return summary


def write_results(
    config: SweepConfig,
    all_results: list[SimulationMetrics],
    summary: list[SummaryEntry],
) -> Path:
    """Write sweep results JSON and return output path."""
    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "config": {
            **asdict(config),
            "output_path": str(output_path),
        },
        "raw_results": all_results,
        "summary": summary,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False, default=str)

    return output_path


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="BlackSwan simulation parameter sweep")
    parser.add_argument("--output", default=str(OUTPUT_DIR / SWEEP_OUTPUT_FILENAME), help="Output JSON path")
    parser.add_argument("--num-agents", type=int, default=NUM_AGENTS)
    parser.add_argument("--steps", type=int, default=TOTAL_STEPS)
    parser.add_argument("--shock-probability", type=float, default=SHOCK_PROBABILITY)
    args = parser.parse_args()

    config = SweepConfig(
        num_agents=args.num_agents,
        steps=args.steps,
        shock_probability=args.shock_probability,
        output_path=Path(args.output),
    )
    run_sweep(config)


def _is_finite(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


if __name__ == "__main__":
    main()