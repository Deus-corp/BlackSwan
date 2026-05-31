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

- ✅ 230+ unit/runtime tests passing.
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
- ✅ Overseer reads memory intelligence from canonical memory heartbeats.
- ✅ Overseer derives memory policy directives from memory intelligence.
- ✅ Memory recognition identifies valuable/review/alert/dedupe candidates.
- ✅ Memory resilience reports primary/fallback/lagging/recovery status.
- ✅ Local CRDT SQLite storage hardened for multi-process devcontainer runtime.
- ✅ `SwarmBrief` protocol for compact LLM-friendly runtime context.
- ✅ Overseer global brief builder from topology and memory intelligence.
- ✅ Cross-swarm `Directive` and `DirectiveResult` protocol.
- ✅ Controlled runtime directive lifecycle validated through CRDT:
  `swarm_directive -> trade command loop -> swarm_directive_result`.
- ✅ Safe trade directive consumer supports `REDUCE_RISK`, `SET_DRY_RUN`, and `OBSERVE`.
- ✅ Runtime directive seed/check helper for development validation.
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
| Swarm contracts/protocols | Canonical runtime foundation | 4 | `src/swarms/common/contracts.py`, `src/swarms/common/protocols/` |
| Swarm topology | 7 first-class swarms registered | 4 | `src/swarms/common/protocols/topology.py` |
| Overseer | Generic topology observer, brief builder, and directive coordinator | 4 | `src/swarms/overseer/` |
| Trade swarm | Mature proving-ground swarm with safe directive consumer | 4 | `src/swarms/trade/` |
| Security swarm | Runtime defensive swarm | 3-4 | `src/swarms/security/` |
| Explorer swarm | Signal discovery swarm | 3 | `src/swarms/explorer/` |
| Improver swarm | Controlled improvement/maintenance swarm | 3 | `src/swarms/improver/` |
| Memory swarm | First-class advisory memory intelligence and resilience swarm | 3-4 | `src/swarms/memory/`, `src/memory/`, `src/intelligence/*memory*` |
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
- builds LLM-friendly global swarm briefs,
- derives safe proposed directives from briefs,
- records directive lifecycle signals through CRDT,

Next:

- stronger policy gates,
- dashboard integration,
- safer restart/repair decisions,
- better distinction between advisory and executable actions.

### Memory

Memory swarm for experience, consolidation, retrieval, and gold sample export.

Current role:

- first-class topology entry,
- canonical heartbeat publisher,
- shared memory ingestion through CRDT,
- quarantine validation for incoming memory records,
- local/own/shared/global memory resilience policy,
- memory recognition and policy actions,
- gold/review/alert/dedupe candidate reporting,
- Overseer-visible memory intelligence,
- advisory-only policy surface.

Next:

- strengthen episodic-to-semantic consolidation,
- expose retrieval quality metrics,
- expand gold sample export workflows,
- add memory dashboards,
- add recovery/fallback drills,
- connect memory directives to safe Overseer actions.

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
- consumes safe CRDT-backed directives such as `REDUCE_RISK`,
- publishes `swarm_directive_result` records after directive application,
- acts as the first runtime proving ground for directive lifecycle validation.

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

### LLM-friendly synchronization layer

The next architecture layer reduces noisy log-driven coordination by introducing explicit context and action records:

```text
SwarmBrief
  -> Directive
  -> DirectiveResult
  -> EvidenceRecord
  -> Memory/Lesson
```

Current status:

* `SwarmBrief` exists as a shared protocol.
* Overseer builds global briefs.
* `Directive` and `DirectiveResult` exist as shared protocols.
* Trade consumes safe directives from CRDT.
* `EvidenceRecord` exists as a shared protocol.
* Controlled helpers publish directive evidence to CRDT.
* Controlled helpers bridge passed evidence into `memory_record`.
* A controlled runtime check validates `REDUCE_RISK` end to end through memory.

Next:

- add EvidenceRecord,
- make Overseer publish selected directives automatically under policy gates,
- add memory-side directive results,
- feed directive outcomes into memory and dashboard views.

### 1. Trade swarm restructuring

Package trade-specific code behind a cleaner swarm boundary:

* separate heartbeat, memory events, execution, risk, portfolio, strategy, and telemetry concerns,
* reduce scattered trade files across `src/trading`, `src/risk`, adapters, and swarm runtime,
* keep `node.py` as a thin runtime orchestration layer,
* preserve green unit/runtime tests at each step.

### 2. Memory swarm maturity

Move from memory intelligence MVP to durable advisory memory:

* consolidate episodic to semantic memory,
* expose retrieval metrics,
* export high-quality training/evaluation samples under explicit gate,
* add memory recovery/fallback drills,
* connect memory directives to safe Overseer policy surfaces.

### 3. Simulation swarm maturity

Move from heartbeat skeleton to scenario executor:

* run configured scenarios,
* evaluate policy candidates,
* publish simulation reports to CRDT/events,
* provide pre-live mutation validation.

### 4. Overseer policy hardening

Improve Overseer so it understands:

* memory intelligence and memory resilience,
* advisory-only swarms,
* executable vs non-executable directives,
* explicit gates for memory/simulation/improver,
* resource-aware spawning,
* stale-node semantics across all swarms.

### 5. Dashboard foundation

Build a local dashboard showing:

* topology health,
* swarm counts,
* current first-class swarms,
* CRDT record counts,
* heartbeats by swarm,
* stale nodes,
* command/event streams,
* memory intelligence,
* memory resilience,
* simulation metrics,
* trade/risk metrics,
* Overseer directives.

### 6. Controlled improver workflow

No more blind bulk model-generated edits.

Required workflow:

1. one file or one small subsystem at a time,
2. patch review,
3. unit tests,
4. runtime smoke,
5. only then continue.

### 7. Documentation update

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
* [x] Shared memory record flow between simulation and memory swarms.
* [x] Memory recognition and gold candidate reporting.
* [x] Memory resilience status in heartbeat.
* [x] Overseer memory intelligence.
* [x] Overseer memory policy directives.
* [x] Multi-process local CRDT storage hardening.
* [x] Memory and simulation first-class topology entries.
* [x] Memory and simulation heartbeat skeletons.
* [x] Overseer sees generic swarm counts.
* [x] `src/cognition`, `src/evolution`, `src/simulation`.
* [x] LLM-friendly `SwarmBrief` protocol.
* [x] Overseer global brief builder.
* [x] Cross-swarm `Directive` and `DirectiveResult` protocols.
* [x] Controlled runtime directive seed/check through CRDT and trade node.
* [x] Runtime directive evidence publishing into CRDT.
* [x] Evidence-to-memory bridge for controlled runtime experience records.
* [x] Runtime directive experience loop documentation.
* [x] Build simulation replay scenarios from runtime evidence memory records.
* [x] Publish replay scenarios into CRDT through a controlled helper.
* [x] Simulation heartbeat reports replay scenario metrics.
* [x] Overseer global brief surfaces simulation replay opportunities.
* [x] Overseer proposes safe `OBSERVE` directives for simulation replay queues.
* [x] Add gated `RUN_REPLAY` directive validation.
* [x] Simulation consumes `RUN_REPLAY` and publishes an explicit rejected result until execution exists.
* [x] `seed_directive` supports JSON payloads for controlled runtime checks.
* [ ] Implement dry-run replay executor for `simulation_replay_scenario`.
* [ ] Dashboard.
* [ ] Better local cluster profiles.
* [ ] Gated `RUN_REPLAY` directive under security validation and policy approval.

### Phase B — Advisory Intelligence

* [x] Memory recognition MVP.
* [x] Memory resilience MVP.
* [ ] Memory retrieval and consolidation.
* [ ] Simulation scenario execution.
* [ ] Policy evaluation before risky actions.
* [ ] Improvement proposals stored as reviewable artifacts.
* [ ] Overseer advisory scoring across all swarms.
* [ ] Evidence protocol for test/runtime/grep validation records.
* [ ] Brief-driven Overseer directive selection under safety gates.
* [ ] Directive outcome memory records.
* [ ] Memory swarm classification of `runtime_evidence` memory records.
* [ ] Overseer brief enrichment from evidence and runtime memory records.

### Phase C — Controlled Autonomy

* [ ] Explicit policy gates.
* [ ] Human-approved upgrade path.
* [ ] Automated regression/smoke pipeline before applying improvements.
* [ ] CRDT-backed audit trail for every action.
* [ ] Safer restart/repair of degraded nodes.
* [ ] Security validation for directives and directive results.
* [ ] Dashboard view for briefs, directives, results, and evidence.

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