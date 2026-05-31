# BlackSwan

**Autonomous, self-improving multi-swarm AI platform.**

BlackSwan is not a trading bot. Trading is one proving ground inside a broader system: an autonomous, self-improving, coordinated swarm platform where multiple specialized swarms share state, memory, simulation results, risk signals, and decisions through a common runtime.

The long-term goal is a system that can launch, observe itself, survive failures, improve its own strategies, test changes in simulation, coordinate specialized swarms, and reduce the amount of direct human intervention to initial bootstrapping and high-level governance.

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)

---

## Project Status: TRL-4+

BlackSwan is currently a laboratory-validated autonomous multi-swarm runtime.

Validated in the current architecture:

- ✅ 230+ unit/runtime tests passing.
- ✅ Trade runtime command loop passing.
- ✅ Swarm runtime smoke test passing.
- ✅ Canonical first-class swarm topology with 7 swarm types:
  - `trade`
  - `security`
  - `explorer`
  - `improver`
  - `overseer`
  - `memory`
  - `simulation`
- ✅ Generic `SwarmHeartbeat`, `SwarmCommand`, `SwarmEvent`, `SwarmPolicy`, and `SwarmCapability` contracts.
- ✅ Overseer sees generic swarm heartbeats and topology health.
- ✅ Memory swarm skeleton publishes canonical `swarm_heartbeat`.
- ✅ Simulation swarm skeleton publishes canonical `swarm_heartbeat`.
- ✅ Canonical engine layers moved into `src/`:
  - `src/cognition`
  - `src/evolution`
  - `src/simulation`
- ✅ `sim/` is now an experiment and compatibility layer, not the core runtime.
- ✅ Industrial CRDT layer with SQLite-backed local persistence.
- ✅ Secure gossip and signed exchange components.
- ✅ Local runtime launcher supports trade, memory, simulation, security, explorer, and overseer services.
- ✅ Simulation and evolution experiments remain runnable through compatibility wrappers.
- Local CRDT runtime storage is hardened for multi-process devcontainer runs with conservative SQLite journaling, process locking, malformed storage detection, and fresh-run cleanup.
- Runtime-level inter-swarm memory flow is validated with Memory + Simulation + Overseer.
- Verified runtime evidence can be converted into `simulation_replay_scenario` records.
- Simulation heartbeat reports replay queue metrics.
- Overseer global briefs surface replay opportunities and propose safe `OBSERVE` directives.
- `RUN_REPLAY` is available as a gated directive: security validates it, simulation consumes it, and execution is rejected until a dry-run executor is implemented.

### Latest Milestone — Memory Intelligence & Resilience

The current runtime now supports explicit shared memory flow, recognition, resilience assessment, and Overseer-level memory intelligence:

- `SimulationSwarmNode` publishes canonical `memory_record` events into CRDT.
- `MemorySwarmNode` refreshes CRDT state from shared SQLite storage.
- `SharedMemoryBridge` ingests explicit memory records through quarantine validation.
- `LocalMemoryAPI` exposes canonical `recall()`, `recent()`, and `stats()` contracts.
- Memory recognition classifies records as new, familiar, duplicate, valuable, risky, or review-worthy.
- Memory policy marks useful records as gold candidates for export/training/evaluation workflows.
- Memory heartbeat reports real memory metrics: total records, accepted shared records, rejected records, skipped records, verified records, record distribution by scope/kind, recognition counts, gold candidates, and resilience status.
- Memory resilience models local, own, shared, and global memory layers with fallback/recovery signals.
- Overseer reads memory intelligence from canonical heartbeats and derives memory directives such as `observe`, `promote_gold`, `review_memory`, `reduce_risk`, and `restore_memory`.

### Latest Milestone — LLM-Friendly Briefs & Runtime Directive Lifecycle

The runtime now includes the first pieces of a structured LLM-friendly synchronization layer:

* `SwarmBrief` provides compact global/swarm/node context for agents instead of raw noisy logs.
* Overseer builds and logs global swarm briefs from topology and memory intelligence.
* `Directive` and `DirectiveResult` provide a lifecycle-aware cross-swarm instruction protocol.
* Overseer can derive safe proposed directives from global briefs.
* Trade nodes can consume safe `swarm_directive` records from CRDT and publish `swarm_directive_result` records.
* A controlled runtime seed check validates the full path:

  * seed `REDUCE_RISK` directive into CRDT,
  * trade command loop refreshes shared CRDT state,
  * trade applies the directive safely,
  * trade publishes an `applied` directive result back to CRDT.
* The trade runtime was stabilized after refactor with regression coverage for:

  * CRDT refresh from shared storage,
  * directive command-loop consumption,
  * evolution/sync no-recursion helpers,
  * `MarketSnapshot` normalization,
  * `TradeFlowService.process()` compatibility,
  * periodic maintenance compatibility.
* Runtime directive evidence can be published back into CRDT as `evidence_record`.
* Verified runtime evidence can be bridged into explicit `memory_record` payloads.
* The full controlled experience loop is documented in `docs/runtime_directive_experience_loop.md`.

---

## Vision

BlackSwan aims to become a distributed autonomous system made of equal cooperating swarms:

- **Overseer** coordinates system-level awareness and policy.
- **Memory** stores, consolidates, retrieves, and exports experience.
- **Simulation** tests policies, counterfactuals, and stress scenarios before live use.
- **Trade** remains a proving ground for risk, capital, execution, and adaptive strategy evolution.
- **Security** protects the runtime and responds to defensive signals.
- **Explorer** discovers external signals and possible opportunities.
- **Improver** proposes controlled project/code improvements.

The project started from a trading swarm because markets provide a useful testbed for resource allocation, uncertainty, risk, feedback loops, and agent performance. The architecture is now being generalized into a platform for autonomous, self-improving, multi-domain swarms.

---

## Architecture Overview

```text
src/
├── cognition/          # Survival, curiosity, meta-policy, belief-state adaptation
├── evolution/          # Genetic/evolution engine and genome primitives
├── simulation/         # Generic environments, agents, and metrics
├── swarms/
│   ├── common/         # Shared contracts, topology, protocols
│   ├── overseer/       # Global coordinator and topology observer
│   ├── trade/          # Trade/risk/evolution proving-ground swarm
│   ├── security/       # Defensive/security swarm
│   ├── explorer/       # Signal discovery and exploration swarm
│   ├── improver/       # Controlled code/project improvement swarm
│   ├── memory/         # Memory recognition, resilience, consolidation/export swarm
│   └── simulation/     # Simulation advisory swarm and scenario runtime
├── core/               # CRDT, gossip, event store, shared runtime primitives
├── memory/             # Memory storage/export/quarantine helpers
├── intelligence/       # LLM clients and memory intelligence components
├── observability/      # Metrics, telemetry, notification utilities
├── testing/            # Runtime smoke and controlled seed/check helpers
└── utils/              # Shared utilities

sim/
├── engine/             # Compatibility wrappers for src.simulation
├── scenarios/          # Experiment scenario configs
├── run.py              # Simulation scenario runner
├── sweep.py            # Parameter sweep runner
├── multi_agent_sim.py  # Multi-agent experiment harness
└── evolve_kelly.py     # Legacy resource-allocation evolution experiment
```

---

## Core Concepts

### Canonical swarm contracts

All swarms are moving toward common envelopes:

* `SwarmHeartbeat`
* `SwarmCommand`
* `SwarmEvent`
* `SwarmCapability`
* `SwarmPolicy`

This lets Overseer, dashboards, CRDT storage, and future orchestration tools treat each swarm as a first-class participant instead of special-casing only the trade swarm.

### LLM-friendly runtime synchronization

BlackSwan is adding a structured synchronization layer so LLM agents and swarm coordinators do not need to reason from noisy logs alone.

Current protocol pieces:

* `SwarmBrief` — compact operational context for global, swarm, or node state.
* `Directive` — lifecycle-aware cross-swarm instruction.
* `DirectiveResult` — acknowledgement, application, rejection, expiration, or failure result.
* Runtime seed/check helpers — controlled development tools for validating directive flow through CRDT.

Validated development flow:

```text
manual/Overseer directive
  -> CRDT shared storage
  -> trade command loop refresh
  -> safe directive application
  -> swarm_directive_result
  -> CRDT audit trail
```

The first validated safe directive is `REDUCE_RISK`, which forces the trade node into a safer dry-run state without enabling live execution.

### Canonical engine layers

The core intelligence primitives now live in `src/`:

* `src/cognition`

  * survival evaluation
  * curiosity/surprise detection
  * meta-policy / Meta-POMDP adaptation
* `src/evolution`

  * genome model
  * genetic engine
  * species/novelty/adaptive mutation
* `src/simulation`

  * scalar stochastic environments
  * simulation agents
  * resource/capital/value metrics

The old `sim/*` modules remain as wrappers and experiment entry points.

### Overseer topology

The canonical topology currently recognizes:

```text
explorer
improver
memory
overseer
security
simulation
trade
```

`memory` and `simulation` are currently advisory-only swarms. They are visible to Overseer and the runtime, but their action surfaces are intentionally gated until policy and dashboard controls mature.

---

### Memory intelligence and resilience

Memory is now treated as a first-class runtime subsystem instead of a passive store.

The current memory path is:

```text
simulation swarm
  -> canonical memory_record
  -> CRDT shared storage
  -> memory quarantine
  -> LocalMemoryAPI
  -> recognition policy
  -> gold/review/alert/dedupe candidates
  -> memory heartbeat
  -> Overseer memory intelligence
  -> Overseer memory directive
```

Memory resilience uses four logical layers:

local  -> fast process-local memory
own    -> durable node/swarm-owned memory
shared -> CRDT/event-backed inter-swarm memory
global -> consolidated memory managed by the memory swarm

The memory swarm publishes resilience signals such as:

- primary_ok
- fallback_active
- shared_bridge_lagging
- degraded
- recovery_needed

Overseer consumes memory intelligence and maps it into policy directives:

- observe
- promote_gold
- review_memory
- reduce_risk
- restore_memory

---

## Quick Start

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan

pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest -q tests/unit/core tests/unit --maxfail=1
python -m src.testing.swarm_runtime_smoke
```

Run simulation experiments:

```bash
python -m sim.run --no-plot
python -m sim.sweep --output artifacts/sim/sweep_results.json
python -m sim.multi_agent_sim
python -m sim.evolve_kelly
```

Run a lightweight local multi-swarm cluster with Overseer, Memory, and Simulation:

```bash
python -m src.swarms.runtime.cluster_cli up \
  --no-trade \
  --no-explorer \
  --no-explorer-meta \
  --no-security \
  --no-security-meta \
  --memory-nodes 1 \
  --simulation-nodes 1 \
  --duration 35 \
  --overseer-interval 10 \
  --safe \
  --echo \
  --no-strict
```

Inspect the latest local cluster:

```bash
python -m src.swarms.runtime.cluster_cli status
python -m src.swarms.runtime.cluster_cli logs --tail 80 overseer memory-1 simulation-1
```

Expected Overseer signal:

```text
Overseer generic swarm counts: {'memory': 1, 'simulation': 1, 'overseer': 1}
Overseer memory intelligence: status=valuable_activity gold=1 directive=promote_gold severity=info
```

---

## Local Runtime Examples

Launch trade plus memory and simulation:

```bash
python -m src.swarms.runtime.cluster_cli up \
  --trade-nodes 2 \
  --memory-nodes 1 \
  --simulation-nodes 1 \
  --duration 120 \
  --overseer-interval 10 \
  --safe \
  --echo
```

Check logs:

```bash
grep -R "Overseer generic swarm counts\|Published memory swarm heartbeat\|Published simulation swarm heartbeat" \
  data/cluster_runtime/latest/logs \
  | tail -100
```

### Controlled runtime directive seed check

Start a local cluster:

```bash
rm -f data/cluster_runtime/latest/ledgers/swarm_crdt.local.db*
rm -f data/cluster_runtime/latest/ledgers/events.local.db*

python -m src.swarms.runtime.cluster_cli up --duration 0 --no-strict
```

In another terminal, seed a safe directive:

```bash
python -m src.testing.seed_directive \
  --action REDUCE_RISK \
  --target trade \
  --target-type swarm \
  --source overseer-seed \
  --directive-id runtime-reduce-risk-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected log:

```text
Published directive result: directive_id=runtime-reduce-risk-1 status=applied
```

Inspect CRDT records:

```bash
python - <<'PY'
from src.core.crdt_adapter import CRDTAdapter

path = "data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
crdt = CRDTAdapter(node_id="debug-reader", db_path=path)
state = getattr(crdt, "state", {}) or {}

for item in state.values():
    if isinstance(item, dict) and item.get("type") in {"swarm_directive", "swarm_directive_result"}:
        print(item.get("type"), item.get("directive_id"), item.get("action"), item.get("status"), item.get("source"), item.get("swarm"))
PY
```

Expected CRDT output:

```text
swarm_directive runtime-reduce-risk-1 REDUCE_RISK issued overseer-seed None
swarm_directive_result runtime-reduce-risk-1 None applied trade-1 trade
```
---

## Documentation

* [Documentation site](https://deus-corp.github.io/BlackSwan/)
* [Roadmap](ROADMAP.md)
* [Runtime directive experience loop](docs/runtime_directive_experience_loop.md)
* [TRL-4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
* [Architecture decisions](docs/architecture/)
* [Formal verification](formal/tla/)
* [Simulation report](docs/TRL4_simulation_baseline.md)
* [Ouroboros Report](docs/TRL4_OUROBOROS_REPORT.md)

---

## Current Development Focus

The current focus is structural hardening:

1. Keep all changes controlled, incremental, and test-backed.
2. Preserve `src/` as the shared platform layer.
3. Keep each swarm self-contained under `src/swarms/<swarm>/`.
4. Continue hardening the LLM-friendly synchronization loop:
   `SwarmBrief -> Directive -> DirectiveResult -> Evidence -> Memory`.
5. Mature `memory` and `simulation` from advisory swarms into active policy-supporting swarms.
6. Keep trade as the proving ground for safe directives, risk controls, runtime evidence, and outcome memory.
7. Build a dashboard that shows topology, swarm health, memory/simulation status, CRDT state, runtime events, Overseer briefs, and directives.
8. Preserve trade as one swarm among equals, not the center of the architecture.

---

## Support the Project

BlackSwan is an independent research project.

If you find it valuable, consider supporting its development:

* Crypto donations — see [DONATIONS.md](DONATIONS.md)

All funds go toward infrastructure, compute resources, and further research. Sponsorship does not confer any rights over the project.

---

## License

Dual-licensed under MIT or Apache-2.0, at your option.

See [LICENSE-MIT](LICENSE-MIT.md) and [LICENSE-APACHE](LICENSE-APACHE.md).

---

*Black Swan © 2026. Technical preprint. Does not constitute financial, legal, investment, operational, or security advice.*