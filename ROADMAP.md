# BlackSwan — Roadmap

**Purpose:** single source of truth for project direction, current maturity, and the path from a laboratory prototype toward an autonomous, self-improving multi-swarm platform.

---

## Vision

BlackSwan is an autonomous multi-swarm platform.

The project is not a trading bot. Trading is one proving ground used to test uncertainty, risk, capital/resource allocation, self-improvement, memory, simulation, and swarm coordination.

The long-term goal is a distributed AI system capable of:

- launching and observing multiple specialized swarms,
- sharing state through CRDT/gossip/event layers,
- preserving memory and learning from experience,
- testing changes in simulation before live use,
- improving strategies under safety gates,
- surviving failures and degraded environments,
- reducing direct human involvement to bootstrapping, high-level policy, and oversight.

---

## Current Status — May 2026

**Overall readiness level: TRL-4+**

Laboratory-validated components now form a working multi-swarm runtime foundation.

### Validated

- ✅ 69+ unit/runtime tests passing.
- ✅ Trade runtime command loop passing.
- ✅ Swarm runtime smoke test passing.
- ✅ Canonical swarm contracts:
  - `SwarmHeartbeat`
  - `SwarmCommand`
  - `SwarmEvent`
  - `SwarmCapability`
  - `SwarmPolicy`
- ✅ Canonical topology registry with 7 first-class swarms:
  - `trade`
  - `security`
  - `explorer`
  - `improver`
  - `overseer`
  - `memory`
  - `simulation`
- ✅ Overseer reads generic swarm heartbeats and reports topology health.
- ✅ Memory swarm skeleton publishes canonical `swarm_heartbeat`.
- ✅ Simulation swarm skeleton publishes canonical `swarm_heartbeat`.
- ✅ Local cluster launcher supports memory and simulation nodes.
- ✅ Core engine layers moved into `src/`:
  - `src/cognition`
  - `src/evolution`
  - `src/simulation`
- ✅ `sim/` converted into experiment/compatibility layer.
- ✅ Legacy simulation runners still work:
  - `sim.run`
  - `sim.sweep`
  - `sim.multi_agent_sim`
  - `sim.evolve_kelly`
- ✅ Industrial CRDT layer: SQLite persistence, deterministic merge, version vectors.
- ✅ Secure gossip and signed exchange components.
- ✅ Genetic/evolution engine generalized beyond trading.
- ✅ Curiosity, survival, and meta-policy components generalized into cognition layer.

---

## Component Map and Readiness

| Subsystem | Status | TRL | Key artifacts |
| :--- | :--- | :---: | :--- |
| Formal models | Core verified | 4 | `formal/tla/*.tla` |
| Core CRDT | Industrial laboratory component | 4 | `src/core/crdt_layer.py`, `src/core/crdt_adapter.py` |
| Gossip layer | Secure prototype | 4 | `src/core/gossip_layer.py`, `src/core/gossip_adapter.py` |
| Swarm contracts | Canonical runtime foundation | 4 | `src/swarms/common/contracts.py` |
| Swarm topology | 7 first-class swarms registered | 4 | `src/swarms/common/protocols/topology.py` |
| Overseer | Generic topology observer and coordinator | 4 | `src/swarms/overseer/` |
| Trade swarm | Mature proving-ground swarm | 4 | `src/swarms/trade/`, `src/trading/` |
| Security swarm | Runtime defensive swarm | 3-4 | `src/swarms/security/` |
| Explorer swarm | Signal discovery swarm | 3 | `src/swarms/explorer/` |
| Improver swarm | Controlled improvement/maintenance swarm | 3 | `src/swarms/improver/` |
| Memory swarm | First-class skeleton, advisory-only | 3 | `src/swarms/memory/`, `src/memory/`, `src/intelligence/*memory*` |
| Simulation swarm | First-class skeleton, advisory-only | 3 | `src/swarms/simulation/`, `src/simulation/` |
| Cognition layer | Canonical engine layer | 4 | `src/cognition/` |
| Evolution layer | Canonical engine layer | 4 | `src/evolution/` |
| Simulation layer | Canonical engine layer | 4 | `src/simulation/` |
| Experiment layer | Compatibility and research runners | 4 | `sim/` |
| D2BFT consensus | Prototype | 3 | `src/core/d2bft.py`, `formal/tla/D2BFT.tla` |
| Dashboard | Planned | 2 | future `dashboard/` or `src/dashboard/` |
| Production deployment | Planned | 2 | future Kubernetes/Helm/deployment artifacts |

---

## First-Class Swarms

### Overseer

Global coordinator and topology observer.

Current role:

- reads CRDT heartbeats/events/commands,
- builds generic topology health,
- emits policy decisions,
- routes directives through canonical/legacy command paths.

Next:

- stronger policy gates,
- dashboard integration,
- safer restart/repair decisions,
- better distinction between advisory and executable actions.

### Memory

Memory swarm for experience, consolidation, retrieval, and gold sample export.

Current role:

- first-class topology entry,
- canonical heartbeat skeleton,
- advisory-only,
- visible to Overseer.

Next:

- connect to `LocalMemoryAPI`,
- consolidate episodic to semantic memory,
- expose retrieval metrics,
- export high-quality training/evaluation samples,
- support memory health dashboards.

### Simulation

Simulation swarm for offline worlds, policy evaluation, counterfactuals, and stress tests.

Current role:

- first-class topology entry,
- canonical heartbeat skeleton,
- advisory-only,
- visible to Overseer.

Next:

- run scenario jobs,
- run policy evaluations,
- run stress tests before live changes,
- publish evaluation results to CRDT/events,
- feed memory and evolution layers.

### Trade

Trade remains a mature proving ground, not the center of the system.

Current role:

- market/risk/evolution runtime,
- dry-run and execution backend support,
- generic heartbeat compatibility,
- canonical imports from `src/cognition` and `src/evolution`.

Next:

- reduce trade-specific assumptions in shared modules,
- improve safety gates,
- feed outcomes into memory and simulation swarms.

### Security

Defensive swarm for firewall, incidents, and vulnerability signals.

Next:

- stronger command safety,
- better event/heartbeat normalization,
- dashboard visibility.

### Explorer

Signal discovery and external observation swarm.

Next:

- stronger sandboxing,
- target governance,
- memory integration.

### Improver

Controlled maintenance and code/project improvement swarm.

Current direction:

- no blind automated file updates,
- all changes should be patch-reviewed and test-backed,
- advisory-first behavior.

Next:

- proposal-only mode by default,
- integration with simulation and memory,
- human-approved controlled application path.

---

## Architectural Direction

### `src/` is the engine

The core platform should live in `src/`.

Target structure:

```text
src/
├── cognition/
├── evolution/
├── simulation/
├── swarms/
│   ├── common/
│   ├── overseer/
│   ├── trade/
│   ├── security/
│   ├── explorer/
│   ├── improver/
│   ├── memory/
│   └── simulation/
├── core/
├── memory/
├── intelligence/
├── trading/
├── risk/
└── observability/
```

### `sim/` is experiments and compatibility

`sim/` should not own core logic.

Current role:

* scenario runners,
* parameter sweeps,
* compatibility wrappers,
* legacy experiment scripts.

Future role:

* research experiments,
* benchmark scenarios,
* offline reports,
* generated artifacts outside source tree.

Generated outputs should go to:

```text
artifacts/sim/
data/sim/
reports/sim/
```

not into source modules.

---

## Immediate Next Steps

### 1. Dashboard foundation

Build a local dashboard showing:

* topology health,
* swarm counts,
* current first-class swarms,
* CRDT record counts,
* heartbeats by swarm,
* stale nodes,
* command/event streams,
* memory metrics,
* simulation metrics,
* trade/risk metrics.

Candidate stack:

* FastAPI or lightweight HTTP server,
* simple HTML/React frontend,
* later Prometheus/Grafana integration.

### 2. Memory swarm maturity

Move from heartbeat skeleton to useful advisory node:

* connect to `LocalMemoryAPI`,
* expose episodic/semantic counts,
* expose consolidation queue,
* publish memory health events,
* export gold samples under explicit gate.

### 3. Simulation swarm maturity

Move from heartbeat skeleton to scenario executor:

* run configured scenarios,
* evaluate policy candidates,
* publish simulation reports to CRDT/events,
* provide pre-live mutation validation.

### 4. Overseer policy hardening

Improve Overseer so it understands:

* advisory-only swarms,
* executable vs non-executable directives,
* explicit gates for memory/simulation/improver,
* resource-aware spawning,
* stale-node semantics across all swarms.

### 5. Controlled improver workflow

No more blind bulk model-generated edits.

Required workflow:

1. one file or one small subsystem at a time,
2. patch review,
3. unit tests,
4. runtime smoke,
5. only then continue.

### 6. Documentation update

Keep README, ROADMAP, and architecture docs aligned with the new concept:

```text
BlackSwan = autonomous multi-swarm platform
not
BlackSwan = trading bot
```

---

## Medium-Term Roadmap

### Phase A — Runtime Foundation

* [x] Canonical swarm contracts.
* [x] Generic swarm topology.
* [x] Memory and simulation first-class topology entries.
* [x] Memory and simulation heartbeat skeletons.
* [x] Overseer sees generic swarm counts.
* [x] `src/cognition`, `src/evolution`, `src/simulation`.
* [ ] Dashboard.
* [ ] Better local cluster profiles.

### Phase B — Advisory Intelligence

* [ ] Memory retrieval and consolidation.
* [ ] Simulation scenario execution.
* [ ] Policy evaluation before risky actions.
* [ ] Improvement proposals stored as reviewable artifacts.
* [ ] Overseer advisory scoring across all swarms.

### Phase C — Controlled Autonomy

* [ ] Explicit policy gates.
* [ ] Human-approved upgrade path.
* [ ] Automated regression/smoke pipeline before applying improvements.
* [ ] CRDT-backed audit trail for every action.
* [ ] Safer restart/repair of degraded nodes.

### Phase D — Production Readiness

* [ ] Stronger secrets handling.
* [ ] More isolation around improver/explorer.
* [ ] Kubernetes/Helm deployment exploration.
* [ ] Observability stack.
* [ ] Long-running stability tests.
* [ ] Formal specs updated for generic multi-swarm topology.

---

## Safety and Scope Notes

BlackSwan is a research system.

Current public code should be treated as laboratory software. Components may simulate capital/resource dynamics, execution, security responses, and self-improvement behavior. These are research mechanisms and do not constitute financial, legal, investment, security, or operational advice.

All autonomous actions should remain gated, logged, test-backed, and reversible.

---

*Black Swan © 2026. Roadmap is hypothetical and subject to change.*