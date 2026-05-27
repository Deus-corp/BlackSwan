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

- ✅ 91+ unit/runtime tests passing.
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

### Latest Milestone — Memory Swarm Foundation

The current runtime now supports explicit shared memory flow between first-class swarms:

- `SimulationSwarmNode` publishes canonical `memory_record` events into CRDT.
- `MemorySwarmNode` refreshes CRDT state from shared SQLite storage.
- `SharedMemoryBridge` ingests explicit memory records through quarantine validation.
- `LocalMemoryAPI` exposes canonical `recall()` and `stats()` contracts.
- Memory heartbeat reports real memory metrics: total records, accepted shared records, rejected records, skipped records, verified records, and record distribution by scope/kind.
- Local cluster runtime supports `--fresh-crdt`, `--memory-ingest-since-start`, and controlled `--memory-ingest-swarm-events`.
- Runtime-level inter-swarm memory flow is validated with Memory + Simulation + Overseer.

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
│   ├── memory/         # Memory swarm skeleton
│   └── simulation/     # Simulation swarm skeleton
├── core/               # CRDT, gossip, event store, shared runtime primitives
├── memory/             # Memory storage/export/quarantine helpers
├── intelligence/       # LLM clients and memory intelligence components
├── trading/            # Trade-specific adapters, execution, market service
├── risk/               # Circuit breakers and exposure/risk management
└── observability/      # Metrics, telemetry, notification utilities

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

---

## Documentation

* [Documentation site](https://deus-corp.github.io/BlackSwan/)
* [Roadmap](ROADMAP.md)
* [TRL-4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
* [Architecture decisions](docs/architecture/)
* [Formal verification](formal/tla/)
* [Simulation report](docs/TRL4_simulation_baseline.md)
* [Ouroboros Report](docs/TRL4_OUROBOROS_REPORT.md)

---

## Current Development Focus

The current focus is structural hardening:

1. Keep all changes controlled, incremental, and test-backed.
2. Continue moving core primitives into `src/`.
3. Keep `sim/` as experiment and compatibility layer.
4. Mature `memory` and `simulation` from heartbeat skeletons into active advisory swarms.
5. Build a dashboard that shows topology, swarm health, memory/simulation status, CRDT state, and runtime events.
6. Preserve trade as one swarm among equals, not the center of the architecture.

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