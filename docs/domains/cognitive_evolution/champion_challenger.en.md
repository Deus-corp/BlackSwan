# Champion/Challenger Model

**Purpose:** Ensure safe introduction of new module versions (code, strategies, configurations) through parallel shadow testing. The model guarantees that no change reaches production until its superiority over the current version is statistically confirmed in a controlled environment.

---

## 1. Overview

Direct deployment of the best genome from the `Genetic Evolution Engine` is risky: even valid code may contain hidden defects that only appear under real load. The «Champion/Challenger» model solves this problem via a two‑step process:

1. **Champion** — the current production version of the module, stably functioning and considered the reference.
2. **Challenger** — a new version that has passed all stages of deterministic validation but has not yet proven its reliability in production‑like conditions.

---

## 2. Genome lifecycle

[Population] → Selection → Mutation → Evaluation
│
└─────────────────────┘
▼
Fitness ≥ threshold?
┌──────┴──────┐
│ │
No Yes
│ │
▼ ▼
Discard Promote to "challenger"
│
▼
Shadow deployment
(in parallel with champion)
│
┌─────────────┴─────────────┐
│ │
Shadow metrics worse? Shadow metrics better?
│ │
▼ ▼
Demote / Discard Promote to "champion"
│
▼
Hot‑reload into production


---

## 3. Promotion criteria

The challenger runs in a separate sandbox with traffic mirroring (or log replay). Comparison with the current champion occurs on key metrics. Promotion (replacement of champion) occurs **only** when **all** of the following conditions are met simultaneously:

| Metric | Promotion condition |
| :--- | :--- |
| **Correctness** | 100% result match with champion on the validation set (deterministic tests) |
| **Throughput** | Not worse than 95% of champion |
| **Latency p95** | Not higher than 105% of champion |
| **Memory** | Not higher than 110% of champion |
| **Uptime** | No crashes during the entire shadow period (≥ 1 hour) |
| **Resilience Score** | ≥ 0.6 (if the module is critical and passed chaos tests) |

If the challenger fails at least one criterion, it is immediately demoted to `Discard`. Results of all shadow tests are saved in `EventBus` as `benchmark_result` and `execution_outcome` artifacts.

---

## 4. Automatic rollback

If after successful promotion the new champion begins to exhibit anomalies in production (increased errors, coherence drop, OOD Circuit Breaker triggering), the system automatically performs a rollback:

1. **Detection:** `OpsMetricsCollector` records that key metrics are out of bounds (thresholds are set in `global_policy.json`).
2. **Decision:** `RecoveryManager` creates a `Proposal` of type `rollback`.
3. **Execution:** Using the `Version Graph` (see [Memory_Hierarchy_Mem0g.md](Memory_Hierarchy_Mem0g.md)), the system atomically replaces the problematic module with the previous champion.
4. **Quarantine:** The problematic genome is placed in the `Quarantine Archive` with a detailed log of the rollback reason.

The entire process takes no more than 10 seconds for non‑critical modules and no more than 60 seconds for critical ones.

---

## 5. Integration with other modules

| Module | Connection |
| :--- | :--- |
| [Genetic_Engine.md](Genetic_Engine.md) | Supplies new candidates (`challenger`), receives feedback on rejection reasons to adjust mutations. |
| [Memory_Hierarchy_Mem0g.md](Memory_Hierarchy_Mem0g.md) | `Version Graph` stores the history of genomes and champion/challenger links. L0 Meta‑Mem0g records promotions and rollbacks for long‑term analysis. |
| [Validation_and_Verification.md](Validation_and_Verification.md) | Challenger passes the full cycle of deterministic validation, benchmarking, and chaos tests before shadow deployment. |
| [Event_Bus_and_Artifact_Model.md](Event_Bus_and_Artifact_Model.md) | All `challenger_promoted`, `champion_rollback` events and corresponding artifacts are published in `EventBus`. |
| [Global_State_and_Decision_Pipeline.md](Global_State_and_Decision_Pipeline.md) | The promotion decision (HardState) goes through Governance with BFT quorum for critical modules. |
| Domain module `Economic_Autonomy` | PPO executors are deployed through Champion/Challenger. Their efficiency directly affects `ROI`. |

---

## 6. Configuration

Model parameters are set in `evolutiond.toml` and `global_policy.json`:

```toml
# evolutiond.toml (fragment)
[champion_challenger]
shadow_duration_sec = 3600          # minimum shadow test time (1 hour)
promotion_quorum = 3               # number of Core Nodes to approve a critical promotion
rollback_threshold_errors = 10     # maximum errors per minute before initiating rollback
rollback_coherency_drop = 0.05     # coherence drop triggering rollback
```
