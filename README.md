# BlackSwan

**Autonomous, self-improving multi-swarm AI platform.**

BlackSwan is a research platform for coordinated autonomous swarms. It is designed around shared runtime state, memory, simulation, security validation, governance records, and controlled execution paths that allow specialized swarms to observe, reason, coordinate, recover, and improve over time.

The system treats autonomy as an auditable lifecycle rather than a direct action loop. Swarms communicate through CRDT-backed records, validated directives, runtime evidence, memory signals, simulation results, risk signals, retry governance, guarded repair flows, and post-action verification.

The long-term goal is a platform that can launch, observe itself, survive failures, test changes in simulation, coordinate specialized swarms, improve its own strategies, and reduce direct human involvement to bootstrapping, policy design, review gates, and high-level governance.

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)

---

## Project Status: TRL-4+

BlackSwan is currently a laboratory-validated autonomous multi-swarm runtime with a verified controlled retry and guarded repair execution loop.

Validated in the current architecture:

* ✅ 940+ tests passing.
* ✅ Retry governance smoke test passing.
* ✅ Swarm runtime smoke test passing.
* ✅ Trade runtime command loop passing.
* ✅ Canonical first-class swarm topology with 7 swarm types:

  * `trade`
  * `security`
  * `explorer`
  * `improver`
  * `overseer`
  * `memory`
  * `simulation`
* ✅ Generic `SwarmHeartbeat`, `SwarmCommand`, `SwarmEvent`, `SwarmPolicy`, and `SwarmCapability` contracts.
* ✅ Overseer sees generic swarm heartbeats, topology health, memory intelligence, replay opportunities, retry governance, and guarded execution readiness.
* ✅ Memory swarm publishes canonical runtime memory signals.
* ✅ Simulation swarm publishes canonical runtime simulation/replay signals.
* ✅ Security validates directive lifecycle, retry governance artifacts, controlled execution artifacts, guarded read-only execution artifacts, repair artifacts, and post-repair verification artifacts.
* ✅ Industrial CRDT layer with SQLite-backed local persistence.
* ✅ Secure gossip and signed exchange components.
* ✅ Local runtime launcher supports trade, memory, simulation, security, explorer, and overseer services.
* ✅ Simulation and evolution experiments remain runnable through compatibility wrappers.
* ✅ Local CRDT runtime storage is hardened for multi-process devcontainer runs with conservative SQLite journaling, process locking, malformed storage detection, and fresh-run cleanup.
* ✅ Runtime-level inter-swarm memory flow is validated with Memory + Simulation + Overseer.
* ✅ Verified runtime evidence can be converted into `simulation_replay_scenario` records.
* ✅ Simulation heartbeat reports replay queue metrics.
* ✅ Overseer global briefs surface replay opportunities and propose safe `OBSERVE` directives.
* ✅ `RUN_REPLAY` is available as a gated directive: security validates it, simulation consumes it, and unsafe execution is rejected unless the controlled path explicitly allows it.
* ✅ Runtime directive evidence can be published back into CRDT as `evidence_record`.
* ✅ Verified runtime evidence can be bridged into explicit `memory_record` payloads.
* ✅ The controlled retry / guarded repair loop is now end-to-end verified through post-repair evidence.

### Latest Milestone — Verified Controlled Retry & Guarded Repair Loop

The current runtime includes a complete, auditable controlled retry and guarded repair execution path:

```text
proposal
  -> approval
  -> execution plan
  -> rendered command
  -> eligibility
  -> controlled execution result
  -> real execution preflight
  -> real execution approval
  -> real execution approval transition
  -> real execution final gate
  -> real execution dry-run envelope
  -> real execution noop harness
  -> read-only promotion
  -> read-only final gate
  -> read-only approval
  -> read-only approval transition
  -> read-only readiness gate
  -> guarded read-only execution
  -> read-only feedback
  -> repair plan
  -> repair action bundle
  -> repair action bundle review
  -> repair approval
  -> repair approval transition
  -> repair final gate
  -> repair dry-run envelope
  -> repair noop harness
  -> repair noop feedback
  -> repair readiness gate
  -> guarded repair execution
  -> post-repair evidence check
  -> close_repair_loop
```

The loop is intentionally fail-closed and audit-first:

* Every stage emits immutable CRDT audit records.
* Inspector summaries verify linkage and orphan counts between stages.
* Security validation rejects missing identifiers, unsafe flags, invalid transitions, or unexpected execution.
* Readiness checks fail on missing stages, unsafe execution flags, broken linkage, or unverified repair outcomes.
* Guarded repair execution requires explicit approval and readiness lineage.
* Post-repair verification confirms all expected repair targets were verified.
* Arbitrary real execution remains disabled.
* The original rendered command is not executed by the guarded repair harness.
* Post-repair evidence may run only the verification subprocess and must not perform additional repair execution.

The final verified runtime state expects:

```text
post_repair_status=passed
repair_outcome_verified=true
repair_targets_expected_count=9
repair_targets_verified_count=9
repair_targets_missing=[]
repair_targets_unexpected=[]
recommended_next_action=close_repair_loop
real_execution_enabled=false
```

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

### Controlled retry and guarded repair execution

BlackSwan now treats retry, execution, repair, and verification as an explicit governance lifecycle rather than a direct command path.

The controlled retry path starts from proposal/approval records, renders a command, checks eligibility, and records blocked or skipped execution safely. The real-execution branch then adds preflight, approval, approval transition, final gate, dry-run envelope, noop harness, read-only promotion, and guarded read-only execution artifacts.

When read-only evidence fails, the system can produce an actionable feedback record, build a repair plan, assemble a repair action bundle, require operator review, require repair approval, run a repair dry-run envelope, run a repair noop harness, publish repair noop feedback, and finally produce a repair readiness gate.

Only after that lineage exists can the guarded repair execution harness run. Even then, it does not execute arbitrary real commands and does not execute the original rendered command. It executes only the controlled guarded repair harness and records the result.

The loop is closed by `replay_lifecycle_retry_post_repair_evidence_check`, which verifies the guarded repair outcome. A successful post-repair check requires:

```text
post_repair_status=passed
repair_outcome_verified=true
post_repair_evidence_exit_code=0
repair_targets_expected_count=9
repair_targets_verified_count=9
repair_targets_missing=[]
repair_targets_unexpected=[]
recommended_next_action=close_repair_loop
```

This gives the runtime an auditable path from failed read-only evidence to reviewed repair, guarded execution, and verified post-repair outcome.

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
* Controlled retry and guarded repair runbook — coming in PR 37.0
* [TRL-4 Validation Report](docs/reports/TRL4_VALIDATION_REPORT.md)
* [Architecture decisions](docs/architecture/)
* [Formal verification](formal/tla/)
* [Simulation report](docs/reports/TRL4_simulation_baseline.md)
* [Ouroboros Report](docs/reports/TRL4_OUROBOROS_REPORT.md)

---

## Current Development Focus

The current focus is milestone stabilization and documentation after the first verified guarded repair loop.

1. Document the controlled retry and guarded repair execution lifecycle.
2. Add an operational runbook for the full golden path:
   `proposal -> guarded repair execution -> post-repair evidence -> close_repair_loop`.
3. Keep all changes controlled, incremental, and test-backed.
4. Preserve `src/` as the shared platform layer.
5. Keep each swarm self-contained under `src/swarms/<swarm>/`.
6. Continue hardening the LLM-friendly synchronization loop:
   `SwarmBrief -> Directive -> DirectiveResult -> Evidence -> Memory`.
7. Keep arbitrary real execution disabled until a separate policy-gated real execution adapter is designed, reviewed, and documented.
8. Keep trade as the proving ground for safe directives, risk controls, runtime evidence, repair loops, and outcome memory.
9. Build dashboard/readiness views that show topology, swarm health, memory/simulation status, CRDT state, runtime events, Overseer briefs, directives, retry governance, guarded execution, repair status, and post-repair verification.
10. Preserve trade as one swarm among equals, not the center of the architecture.

Near-term milestone plan:

```text
PR 37.0 — milestone documentation and operational runbook
PR 37.1 — final golden-path smoke script
PR 37.2 — docs/schema/test fixture cleanup
PR 38.x — policy-gated real execution adapter scaffold
```

Out of scope until a separate reviewed milestone:

* arbitrary real execution
* external side effects outside guarded harnesses
* production policy scheduler
* multi-proposal batch repair execution
* autonomous code-changing execution without explicit review gates

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