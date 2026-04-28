# BlackSwan TRL-4 Simulation Baseline (first run)

Date: 2026-04-28
Configuration: 6 agents (3 Kelly, 3 Random), 100 steps, burn=0.5, drift=0.002, volatility=0.01

| Metric | Value |
|--------|-------|
| Agents alive | 0 |
| Survival rate | 0.0 |
| Kelly avg capital | 1123.66 |
| Random avg capital | 926.07 |
| Total trades | 236 |

All agents died due to burn rate and commissions. Next step: parameter sweep to find stable survival zone.

# BlackSwan TRL-4 Simulation Sweep Results

Date: 2026-04-28
Sweep parameters: burn_rate ∈ {0, 0.1, 0.2, 0.5, 1.0}, failure_prob ∈ {0, 0.01, 0.05, 0.1}, 3 seeds each.
Agents: 6 (3 Kelly, 3 Random), 200 steps.

## Optimal Stability Zone
- failure_prob = 0.0, burn_rate ≤ 1.0:
  * Survival rate: 100%
  * Kelly avg capital: 2025–2369
  * Random avg capital: 604–804
  * Kelly advantage: ~1400–1565

Selected for TRL-4 Docker demo: **burn_rate=0.1, failure_prob=0.0**.