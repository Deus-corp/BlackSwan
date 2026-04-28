#!/usr/bin/env python3
import sys, os, itertools, json, statistics, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sim.multi_agent_sim import SimulationConfig, MultiAgentSimulation

burn_values = [0.0, 0.1, 0.2, 0.5, 1.0]
failure_values = [0.0, 0.01, 0.05, 0.1]
seeds = list(range(3))  # 3 повтора для каждой комбинации

results = []
for burn, fail, seed in itertools.product(burn_values, failure_values, seeds):
    random.seed(seed)
    config = SimulationConfig(
        num_agents=6, steps=200, burn_rate_per_step=burn,
        agent_failure_prob=fail, shock_probability=0.0
    )
    sim = MultiAgentSimulation(config)
    metrics = sim.run()
    metrics.update({"burn_rate": burn, "failure_prob": fail, "seed": seed})
    results.append(metrics)

# Группируем и усредняем
grouped = {}
for r in results:
    key = (r["burn_rate"], r["failure_prob"])
    grouped.setdefault(key, []).append(r)
summary = []
for (burn, fail), lst in grouped.items():
    avg_alive = statistics.mean(r["agents_alive"] for r in lst)
    avg_kelly = statistics.mean(r["kelly_avg_capital"] for r in lst)
    avg_random = statistics.mean(r["random_avg_capital"] for r in lst)
    summary.append({
        "burn_rate": burn,
        "failure_prob": fail,
        "avg_alive": avg_alive,
        "avg_kelly": avg_kelly,
        "avg_random": avg_random,
        "kelly_advantage": avg_kelly - avg_random
    })

summary.sort(key=lambda x: (x["avg_alive"], x["kelly_advantage"]), reverse=True)
print("Parameter sweep summary (best survival first):")
for s in summary:
    print(f"burn={s['burn_rate']:.2f}, fail={s['failure_prob']:.3f}: alive={s['avg_alive']:.1f}, Kelly={s['avg_kelly']:.1f}, Random={s['avg_random']:.1f}, advantage={s['kelly_advantage']:.1f}")

with open("sim/sweep_results.json", "w") as f:
    json.dump({"config": {"steps":200, "agents":6}, "raw": results, "summary": summary}, f, indent=2)