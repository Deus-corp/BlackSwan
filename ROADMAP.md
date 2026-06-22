# BlackSwan — Roadmap

**Purpose:** single source of truth for project direction, current maturity, and the path from a laboratory prototype toward an autonomous, self-improving multi-swarm AI platform.

---

## Vision

BlackSwan is an autonomous, self-improving multi-swarm AI platform.

It is designed as a distributed runtime where specialized swarms share state, evidence, memory, simulation results, governance records, and controlled execution signals through CRDT, gossip, and event layers.

The platform is organized around first-class cooperating swarms:

- **Overseer** coordinates system-level awareness, topology health, policy, and cross-swarm directives.
- **Memory** stores, consolidates, retrieves, and routes runtime experience and evidence.
- **Simulation** tests policies, counterfactuals, replay scenarios, and stress cases before live use.
- **Security** validates directives, governance records, guarded execution, repair artifacts, and post-action evidence.
- **Explorer** performs read-only external observation, source discovery, evidence collection, and handoff to Memory.
- **Improver** proposes controlled project and code improvements under review gates.
- **Trade** remains one specialized proving-ground swarm within the broader multi-swarm platform.

The long-term goal is a distributed AI system capable of:

- launching and observing multiple specialized swarms,
- sharing runtime state through CRDT, gossip, and event layers,
- preserving memory and learning from experience,
- testing changes in simulation before live use,
- coordinating controlled improvements under safety gates,
- surviving failures and degraded environments,
- verifying outcomes through auditable evidence,
- reducing direct human involvement to bootstrapping, high-level policy, review gates, and oversight.

---

## Current Status — June 2026

**Overall readiness level: TRL-4+**

BlackSwan is now a laboratory-validated autonomous multi-swarm runtime with a verified controlled retry and guarded repair execution loop.

The latest verified additions since the last roadmap update include:

* ✅ Explorer network‑read evidence loop end‑to‑end (goal → memory_record).
* ✅ Explorer‑Memory replay smoke contract and yield metrics.
* ✅ Cluster latest artifacts lifecycle (index, retention, cleanup).
* ✅ Closed sandbox execution substrate (fail‑closed pre‑execution contour).
* ✅ Controlled retry and guarded repair runbook with golden‑path smoke.

The current milestone is no longer only "directive lifecycle through CRDT". The system now has an auditable path from failed read-only evidence to reviewed repair, guarded repair execution, and post-repair evidence verification.

### Validated

* ✅ 1435+ tests passing.
* ✅ Retry governance smoke test passing.
* ✅ Swarm runtime smoke test passing.
* ✅ Trade runtime command loop passing.
* ✅ Canonical swarm contracts:

  * `SwarmHeartbeat`
  * `SwarmCommand`
  * `SwarmEvent`
  * `SwarmCapability`
  * `SwarmPolicy`
* ✅ Canonical topology registry with 7 first-class swarms:

  * `trade`
  * `security`
  * `explorer`
  * `improver`
  * `overseer`
  * `memory`
  * `simulation`
* ✅ Overseer reads generic swarm heartbeats and reports topology health.
* ✅ Overseer reads memory intelligence from canonical memory heartbeats.
* ✅ Overseer derives memory policy directives from memory intelligence.
* ✅ Memory recognition identifies valuable/review/alert/dedupe candidates.
* ✅ Memory resilience reports primary/fallback/lagging/recovery status.
* ✅ Local CRDT SQLite storage hardened for multi-process devcontainer runtime.
* ✅ `SwarmBrief` protocol for compact LLM-friendly runtime context.
* ✅ Overseer global brief builder from topology, memory intelligence, retry governance, and guarded execution signals.
* ✅ Cross-swarm `Directive` and `DirectiveResult` protocol.
* ✅ Controlled runtime directive lifecycle validated through CRDT:
  `swarm_directive -> trade command loop -> swarm_directive_result`.
* ✅ Safe trade directive consumer supports `REDUCE_RISK`, `SET_DRY_RUN`, and `OBSERVE`.
* ✅ Runtime directive seed/check helper for development validation.
* ✅ Runtime directive evidence publishing into CRDT.
* ✅ Evidence-to-memory bridge for controlled runtime experience records.
* ✅ Runtime directive experience loop documentation.
* ✅ Build simulation replay scenarios from runtime evidence memory records.
* ✅ Publish replay scenarios into CRDT through a controlled helper.
* ✅ Simulation heartbeat reports replay scenario metrics.
* ✅ Overseer global brief surfaces simulation replay opportunities.
* ✅ Overseer proposes safe `OBSERVE` directives for simulation replay queues.
* ✅ Gated `RUN_REPLAY` directive validation.
* ✅ Simulation consumes `RUN_REPLAY` and publishes explicit rejected/blocked results until execution is allowed by the controlled path.
* ✅ Controlled retry governance trail with proposal, approval, plan, rendered command, eligibility, result, and controlled execution result.
* ✅ Real-execution preflight, approval, transition, final gate, dry-run envelope, noop harness, and linkage observability.
* ✅ Guarded read-only execution path with read-only approval, readiness gate, execution result, feedback, and repair planning.
* ✅ Repair plan, repair action bundle, bundle review, repair approval, repair approval transition, repair final gate, repair dry-run envelope, repair noop harness, repair noop feedback, and repair readiness gate.
* ✅ Guarded repair execution harness with explicit allow flag, immutable audit record, and no arbitrary real execution.
* ✅ Post-repair evidence check verifies the guarded repair outcome and closes the repair loop.
* ✅ Security validation, inspector summaries, readiness reports, and docs tests cover the controlled retry / guarded repair lifecycle.
* ✅ Memory swarm skeleton publishes canonical `swarm_heartbeat`.
* ✅ Simulation swarm skeleton publishes canonical `swarm_heartbeat`.
* ✅ Local cluster launcher supports memory and simulation nodes.
* ✅ Core engine layers moved into `src/`:

  * `src/cognition`
  * `src/evolution`
  * `src/simulation`
* ✅ `sim/` converted into experiment/compatibility layer.
* ✅ Legacy simulation runners still work:

  * `sim.run`
  * `sim.sweep`
  * `sim.multi_agent_sim`
  * `sim.evolve_kelly`
* ✅ Industrial CRDT layer: SQLite persistence, deterministic merge, version vectors.
* ✅ Secure gossip and signed exchange components.
* ✅ Genetic/evolution engine generalized beyond trading.
* ✅ Curiosity, survival, and meta-policy components generalized into cognition layer.
* ✅ Explorer `network_read` execution loop from explicit evidence seed to fetched finding, `USEFUL` classification, memory handoff quality gate, and structured `memory_record`.
* ✅ Explorer → Memory replay smoke and yield metrics validated.
* ✅ Cluster latest artifacts lifecycle (index, retention, cleanup dry‑run and execute gate).
* ✅ Closed policy‑gated sandbox execution substrate through rendered command validation scaffold.
* ✅ Controlled retry and guarded repair runbook with golden‑path smoke.
* ✅ Latest runtime artifacts lifecycle operator checklist.
* ✅ Explorer runtime results can be replayed into deterministic Memory evidence queries through a contract-checked replay artifact.
* ✅ Memory replay smoke emits detailed `memory_replay_yield` metrics and compact `memory_replay_summary` operator metrics.
* ✅ Latest runtime artifacts can be persisted under `data/cluster_runtime/latest/artifacts/`, inspected, indexed, contract-checked, and retention-audited.
* ✅ Latest artifact cleanup supports dry-run by default, an explicit execute-local-artifacts gate, and post-cleanup verification summaries.

### Latest verified loop

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

Expected final verification signals:

```text
post_repair_status=passed
repair_outcome_verified=true
post_repair_evidence_exit_code=0
repair_targets_expected_count=9
repair_targets_verified_count=9
repair_targets_missing=[]
repair_targets_unexpected=[]
recommended_next_action=close_repair_loop
real_execution_enabled=false
```

### Safety boundary

The verified loop does not mean arbitrary real execution is enabled.

Current safety boundary:

* arbitrary real execution remains disabled;
* the original rendered command is not executed by the guarded repair harness;
* repair execution requires explicit approval and readiness lineage;
* guarded repair execution executes only the controlled repair harness;
* post-repair evidence check may execute only the verification subprocess;
* every stage emits immutable CRDT audit records;
* readiness fails closed on missing linkage, orphan records, unsafe flags, or unverified repair outcomes.

See the [Controlled Retry and Guarded Repair Runbook](docs/controlled_retry_guarded_repair_runbook.md) for the exact operator checklist and golden‑path smoke.

---

## Current Phase — Swarm Execution Transition

The sandbox execution substrate is now closed as a reusable fail-closed
pre-execution contour.

Completed substrate:

```text
real execution adapter contract
real execution adapter request schema
capability policy matrix
sandbox adapter scaffold
sandbox adapter request preflight
sandbox request envelope scaffold
sandbox materialization preflight scaffold
sandbox workspace plan scaffold
sandbox workspace preparation preflight scaffold
sandbox input materialization plan scaffold
sandbox command render plan scaffold
sandbox rendered command scaffold
sandbox rendered command validation scaffold
```

The final substrate state is intentionally blocked before execution:

```text
sandbox_rendered_command_validation_scaffold_observed=true
sandbox_rendered_command_validation_scaffold_linkage_complete=true
sandbox_rendered_command_validation_scaffold_orphans=0
sandbox_rendered_command_validation_scaffold_status=blocked
sandbox_rendered_command_validation_scaffold_fail_closed=true
sandbox_rendered_command_validation_scaffold_deny_by_default=true
sandbox_rendered_command_validation_enabled=false
sandbox_rendered_command_validation_performed=false
sandbox_rendered_command_validation_passed=false
sandbox_rendered_command_validation_failed=false
sandbox_rendered_command_executable=false
sandbox_rendered_command_validated=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

### Transition decision

The scaffold contour is closed for normal development. Future scaffold or
readiness expansion should be reserved for dangerous execution classes only.

The default development direction is now useful swarm behavior and controlled
execution.

### Execution risk tiers

The completed sandbox substrate and the guarded repair runbook serve as reusable safety contours. Future development follows the risk tier model.

```text
safe_local_execution
  Local sandbox-only commands.
  May run allowlisted subprocesses.
  May write only inside an ephemeral sandbox workspace.
  Must not access secrets, production paths, network writes, wallets, or external APIs.

network_read
  Internet or API reads.
  Used by explorer/data-gathering swarms.
  Requires rate limits, source attribution, freshness tracking, and storage boundaries.

testnet_external_write
  Real external execution on testnets only.
  Includes Sepolia trading/swaps with test wallets and explicit testnet configuration.
  Does not require simulation by default, but still requires capability policy,
  explicit network identity, budget/cap limits, and operator-visible records.

external_write_stub
  Non-testnet external writes such as posting messages, modifying GitHub,
  sending email, or writing to third-party APIs.
  Stubbed until explicitly approved per capability.

production_financial_write
  Mainnet swaps, transfers, approvals, CEX orders, withdrawals, leverage, or
  irreversible financial actions.
  Blocked until a separate explicit production policy milestone.

system_dangerous_stub
  Host-destructive or production-destructive operations such as rm outside
  sandbox, chmod/chown, service restart, docker control, package installation,
  credential access, or production database mutation.
  Stubbed unless explicitly approved in a dedicated safety PR.
```

### Next priorities

```text
P0 — Explorer swarm execution
  - ✅ completed: explicit evidence seed → network_read → finding → USEFUL → memory_record
  - ✅ completed: research goal → source planner → high‑priority evidence candidates (via safe public search templates)
  - ✅ completed: Explorer‑Memory replay smoke and yield metrics
  - next: source‑specific adapters, freshness/ranking, deduplication, richer handoff to Memory

P0 — Memory swarm execution
  - ingestion
  - normalization
  - deduplication
  - classification
  - summarization
  - retrieval/indexing
  - retention/archive policy
  - evidence routing
  - ✅ completed: memory evidence catalog, deterministic retrieval, vector‑ready schema, heartbeat telemetry

P1 — Safe local execution
  - allowlisted local sandbox subprocess
  - sandbox-only file writes
  - stdout/stderr/exit code evidence
  - no secrets
  - no production paths

P1 — Testnet external write execution
  - Sepolia/testnet wallets
  - explicit testnet config
  - small caps/budgets
  - no mainnet
  - no production funds

P2 — Production/mainnet execution
  - separate approval contour
  - capability-specific policies
  - operator authorization
  - explicit caps
  - rollback/evidence requirements
```

### Explorer architecture direction

Explorer should keep the meta-agent pattern because internet research parallelizes
naturally by source, topic, freshness, and quality checks.

```text
overseer
  coordinates swarm meta-agents

explorer meta-agent
  decomposes research goals
  assigns source/node tasks
  merges findings
  decides when evidence is sufficient
  hands structured evidence to memory

explorer nodes
  web search/read nodes
  source-specific collectors
  freshness/ranking nodes
  evidence extraction nodes
  quality/conflict check nodes
```

Explorer should start with `network_read` execution only. It should not perform
external writes.

### Explorer execution milestone

Explorer has now crossed from scaffolded swarm behavior into useful read-only execution.

Verified loop:

```text
research goal
  -> evidence seed target
  -> explorer_targets
  -> network_read fetch
  -> explorer_finding
  -> USEFUL classification
  -> memory handoff quality gate
  -> memory_record
```

Runtime success criteria:

```text
source_adapter_targets_seen.evidence_seed >= 1
source_adapter_targets_selected.evidence_seed >= 1
findings_emitted > 0
classifications_published > 0
total_memory_records_published > 0
```

This establishes the first Explorer-to-Memory execution bridge. The remaining Explorer work is no longer basic execution proof; it is autonomous research quality:

```text
research goal
  -> source plan
  -> high-priority evidence candidates
  -> source-specific collection
  -> freshness/authority/quality scoring
  -> dedupe/conflict checks
  -> memory handoff
```

Explorer remains `network_read` only. External writes, private data access, credential use, production mutation, and financial execution are out of scope for Explorer.

### Memory architecture direction

Memory does not need many autonomous agents at first. Start with one memory
meta-agent plus deterministic worker components.

```text
memory meta-agent
  decides what should be remembered, indexed, archived, or discarded

workers/components
  ingest
  normalize
  dedupe
  classify
  summarize
  index
  retrieve
  retain/archive
  route evidence to swarms
```

Split memory into multiple autonomous nodes only after volume, latency,
specialization, or fault-isolation pressure requires it.

---

## Component Map and Readiness

| Subsystem | Status | TRL | Key artifacts |
| :--- | :--- | :---: | :--- |
| Formal models | Core verified | 4 | `formal/tla/*.tla` |
| Core CRDT | Industrial laboratory component | 4 | `src/core/crdt_layer.py`, `src/core/crdt_adapter.py` |
| Gossip layer | Secure prototype | 4 | `src/core/gossip_layer.py`, `src/core/gossip_adapter.py` |
| Swarm contracts/protocols | Canonical runtime foundation | 4 | `src/swarms/common/contracts.py`, `src/swarms/common/protocols/` |
| Swarm topology | 7 first-class swarms registered | 4 | `src/swarms/common/protocols/topology.py` |
| Overseer | Generic topology observer, brief builder, directive coordinator, retry/repair observability consumer | 4 | `src/swarms/overseer/` |
| Trade swarm | Mature proving-ground swarm with safe directive consumer | 4 | `src/swarms/trade/` |
| Security swarm | Runtime defensive swarm with directive, retry, guarded execution, repair, and post-repair validation | 4 | `src/swarms/security/` |
| Explorer swarm | Network-read evidence execution with explicit evidence seed to `memory_record`; source planning and autonomous research quality still maturing | 3-4 | `src/swarms/explorer/` |
| Improver swarm | Controlled improvement/maintenance swarm, advisory-first and review-gated | 3 | `src/swarms/improver/` |
| Memory swarm | First-class advisory memory intelligence and resilience swarm | 3-4 | `src/swarms/memory/`, `src/memory/`, `src/intelligence/*memory*` |
| Simulation swarm | First-class advisory replay/evidence swarm with gated execution surfaces | 3-4 | `src/swarms/simulation/`, `src/simulation/` |
| Cognition layer | Canonical engine layer | 4 | `src/cognition/` |
| Evolution layer | Canonical engine layer | 4 | `src/evolution/` |
| Simulation layer | Canonical engine layer | 4 | `src/simulation/` |
| Experiment layer | Compatibility and research runners | 4 | `sim/` |
| Controlled retry / guarded repair loop | End-to-end verified laboratory lifecycle from retry proposal to post-repair evidence | 4 | `src/testing/*retry*`, `src/testing/*repair*`, `src/swarms/security/runtime_validation.py` |
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
- surfaces controlled retry, guarded execution, repair, and post-repair verification metrics in global briefs,
- keeps guarded execution and repair status visible without enabling arbitrary real execution,

Next:

- stronger policy gates,
- dashboard integration,
- safer restart/repair decisions,
- better distinction between advisory and executable actions.
- dashboard integration,
- milestone/golden-path runbook visibility,
- stronger policy gates for future real execution adapters,
- safer restart/repair decisions,
- better distinction between advisory, dry-run, noop, guarded read-only, guarded repair, and arbitrary real execution actions.

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

* See the [Cluster Latest Artifacts Lifecycle](docs/cluster_latest_artifacts_lifecycle.md) for ingestion, catalog, and replay smoke workflows.

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

Defensive swarm for firewall, incidents, vulnerability signals, directive validation, and execution governance.

Current role:

- validates directive and directive-result records,
- validates retry governance records,
- validates controlled execution records,
- validates real-execution preflight/approval/final-gate/dry-run/noop artifacts,
- validates guarded read-only execution artifacts,
- validates repair plan, repair action bundle, review, approval, transition, final gate, dry-run, noop, feedback, readiness, guarded execution, and post-repair evidence artifacts,
- rejects unsafe execution flags, missing linkage identifiers, invalid transitions, orphaned records, and unverified repair outcomes,
- keeps arbitrary real execution disabled unless a future policy-gated adapter is explicitly introduced.

The full validation and repair lifecycle is documented in the [Controlled Retry and Guarded Repair Runbook](docs/controlled_retry_guarded_repair_runbook.md).

Next:

- dashboard visibility,
- policy-gated real execution adapter scaffold,
- richer incident/event heartbeat normalization,
- stricter production isolation and secret handling.

### Explorer

Read-only signal discovery, external observation, and evidence collection swarm.

Current role:

* first useful `network_read` execution bridge,
* explicit research/evidence seed ingestion,
* source adapter target scheduling,
* public network fetches under policy and robots handling,
* link discovery and frontier scheduling,
* source quality, freshness, authority, and relevance scoring,
* useful finding classification,
* memory handoff quality gate,
* structured `memory_record` publication for high-value evidence.

Verified execution loop:

```text
goal/evidence seed -> network read -> finding -> USEFUL -> memory_record
```

Next:

* research-goal source planner,
* automatic high-priority evidence candidate generation,
* stronger source-specific adapters,
* better HTML/content extraction,
* duplicate and conflict handling,
* richer evidence summaries for Memory and Improver,
* long-running network-read stability checks.

The Explorer → Memory replay path and artifact lifecycle are described in the [Cluster Latest Artifacts Lifecycle](docs/cluster_latest_artifacts_lifecycle.md).

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

### LLM-friendly synchronization and execution governance layer

The current architecture reduces noisy log-driven coordination by introducing explicit context, action, evidence, memory, retry, repair, and verification records:

```text
SwarmBrief
  -> Directive
  -> DirectiveResult
  -> EvidenceRecord
  -> Memory/Lesson
  -> RetryGovernance
  -> ControlledExecution
  -> GuardedReadOnlyExecution
  -> RepairPlan
  -> GuardedRepairExecution
  -> PostRepairEvidence
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
* Retry governance records proposal, approval, plan, rendered command, eligibility, and result lineage.
* Controlled execution records safe skipped/rejected execution results.
* Real-execution preflight/approval/final-gate/dry-run/noop records prove a blocked real-execution path without arbitrary execution.
* Guarded read-only execution can run a controlled read-only evidence path and record feedback.
* Repair planning can produce reviewed repair action bundles under explicit gates.
* Guarded repair execution can run the controlled repair harness after approval/readiness lineage.
* Post-repair evidence verification can close the loop with `close_repair_loop`.
* Security, inspector, readiness, and docs tests surface the full lineage.

Next:

* document the golden-path runbook,
* add a single golden-path smoke script,
* add dashboard views for retry/repair/post-repair verification,
* keep arbitrary real execution disabled until a separate policy-gated adapter milestone.

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

**Phase completion summary (June 2026)**:

- Phase A — Runtime Foundation: **98%** complete (remaining: golden‑path smoke script, dashboard views, cluster profiles).
- Phase B — Advisory Intelligence: **~85%** complete (explorer source planner, memory dedup/index/routing, simulation execution remain).
- Phase C — Controlled Autonomy: **~80%** complete (dashboard views, golden‑path smoke, policy‑gated real adapter scaffold remain).
- Phase D — Production Readiness: **~20%** complete (secrets, deployment, observability, long‑running tests remain).

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
* [x] Close replay evidence loop from simulation execution to evidence, memory, MemorySummary, Overseer intelligence, and global brief visibility.
* [x] Controlled retry governance trail from proposal to controlled execution result.
* [x] Real-execution preflight, approval, transition, final gate, dry-run envelope, and noop harness.
* [x] Read-only promotion, read-only approval, readiness, guarded read-only execution, and feedback.
* [x] Repair plan, repair action bundle, bundle review, repair approval, transition, final gate, dry-run envelope, noop harness, and noop feedback.
* [x] Repair readiness gate and guarded repair execution harness.
* [x] Post-repair evidence check verifies repair outcome and emits `close_repair_loop`.
* [x] Security/Inspector/Readiness surface the verified guarded repair lifecycle.
* [x] Closed fail-closed policy-gated sandbox execution substrate through rendered command validation scaffold.
* [x] Explorer explicit evidence seed can execute `network_read` and publish a useful `memory_record`.
* [x] Explorer-to-Memory read-only evidence bridge validated in runtime.
* [x] Explorer runtime memory replay artifact and query contract smoke.
* [x] Memory replay smoke yield and compact summary metrics.
* [x] Latest runtime artifact persistence under `data/cluster_runtime/latest/artifacts/`.
* [x] Latest artifacts index, retention inspection, cleanup dry-run, execute-local gate, and post-cleanup verification.
* [x] Latest artifacts lifecycle operator checklist.
* [x] Explorer → Memory replay smoke, yield metrics, latest artifact lifecycle.
* [x] Cluster latest artifacts index, retention inspection, cleanup (dry‑run + execute gate).
* [x] Closed policy‑gated sandbox execution substrate.
* [x] Controlled retry and guarded repair runbook with golden‑path smoke.
* [ ] Golden-path smoke script for the full controlled retry / guarded repair lifecycle.
* [ ] Dashboard views for retry governance, guarded execution, repair status, and post-repair evidence.
* [ ] Better local cluster profiles.

### Phase B — Advisory Intelligence

* [x] Memory recognition MVP.
* [x] Memory resilience MVP.
* [x] Evidence protocol for test/runtime/grep validation records.
* [x] Brief-driven Overseer directive visibility under safety gates.
* [x] Directive outcome memory records.
* [x] Memory swarm classification of `runtime_evidence` memory records.
* [x] Overseer brief enrichment from evidence and runtime memory records.
* [x] Explorer useful evidence can be handed off to Memory as structured `memory_record`.
* [x] Explorer → Memory replay smoke validates deterministic Memory retrieval from replayable runtime evidence artifacts.
* [x] Memory replay summaries expose operator-facing evidence yield metrics for future dashboards.
* [x] Explorer source‑planned evidence loop with safe public search templates.
* [x] Memory evidence catalog, deterministic retrieval, vector‑ready schema, heartbeat telemetry.
* [x] Explorer‑Memory replay smoke yield metrics and compact summary.
* [ ] Research-goal source planner generates high-priority evidence candidates without manual evidence URLs.
* [ ] Memory deduplicates, indexes, summarizes, and routes Explorer evidence to Improver and Overseer.
* [ ] Dashboard-ready summary cards for memory, replay, retry, repair, and post-repair verification.
* [ ] Memory retrieval and consolidation.
* [ ] Simulation scenario execution.
* [ ] Policy evaluation before risky actions.
* [ ] Improvement proposals stored as reviewable artifacts.
* [ ] Overseer advisory scoring across all swarms.

### Phase C — Controlled Autonomy

* [x] Explicit policy gates for directive validation.
* [x] CRDT-backed audit trail for controlled retry and guarded repair actions.
* [x] Security validation for directives, directive results, retry governance, guarded execution, repair, and post-repair verification records.
* [x] Human-reviewed repair path through repair action bundle review and repair approval transition.
* [x] Automated regression/smoke pipeline before continuing controlled repair work.
* [x] Guarded repair execution and post‑repair evidence verification loop closed.
* [x] Controlled retry and guarded repair runbook and golden‑path smoke.
* [ ] Dashboard view for briefs, directives, results, evidence, retry governance, repair, and post-repair verification.
* [ ] Golden-path smoke script that runs the full verified loop.
* [ ] Safer restart/repair of degraded runtime nodes.
* [ ] Policy-gated real execution adapter scaffold.

### Phase D — Production Readiness

* [ ] Stronger secrets handling.
* [ ] More isolation around improver/explorer.
* [ ] Kubernetes/Helm deployment exploration.
* [ ] Observability stack.
* [ ] Long-running stability tests.
* [ ] Formal specs updated for generic multi-swarm topology.
* [ ] Production-safe policy engine for real execution adapter authorization.
* [ ] Immutable audit export for retry/repair/post-repair evidence records.
* [ ] Long-running golden-path stability tests.

---

## Safety and Scope Notes

BlackSwan is a research system.

Current public code should be treated as laboratory software. Components may simulate capital/resource dynamics, execution, security responses, memory, simulation, retry governance, and self-improvement behavior. These are research mechanisms and do not constitute financial, legal, investment, security, or operational advice.

The current verified guarded repair loop does not enable arbitrary real execution. It proves that the system can:

* observe failed read-only evidence,
* produce actionable feedback,
* build and review a repair plan,
* require explicit repair approval,
* prepare repair dry-run and noop records,
* publish a repair readiness gate,
* run a guarded repair harness,
* verify the post-repair outcome,
* close the repair loop through CRDT audit records.

All autonomous actions should remain gated, logged, test-backed, auditable, and reversible.

Out of scope until a separate reviewed milestone:

* arbitrary real execution,
* external side effects outside controlled harnesses,
* production policy scheduling,
* multi-proposal batch repair execution,
* autonomous code-changing execution without explicit review gates.

---

*Runtime runbooks: [Controlled Retry & Guarded Repair](docs/controlled_retry_guarded_repair_runbook.md) | [Cluster Artifacts Lifecycle](docs/cluster_latest_artifacts_lifecycle.md)*

---

*Black Swan © 2026. Roadmap is hypothetical and subject to change.*