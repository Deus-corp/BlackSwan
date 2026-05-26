# BlackSwan — Roadmap

**Purpose:** single source of truth for project progress, current architecture, and next milestones.

BlackSwan is moving from a laboratory prototype toward a modular autonomous swarm runtime with guarded testnet execution, CRDT coordination, self-improvement loops, and operator-facing observability.

---

## 🔭 Vision

Create a distributed AI swarm capable of:

- surviving operational failures,
- coordinating through decentralized state,
- improving strategies through evolutionary search,
- using LLMs for bounded mutation and reasoning,
- executing only through explicit safety gates,
- exposing transparent runtime state for operators and future dashboards.

The long-term direction is an autonomous, self-improving, self-healing system that preserves hard safety boundaries.

---

## 📍 Current Status — May 2026

**Overall readiness:** TRL-5 research prototype.

The system now has a modular runtime, CRDT-visible heartbeats and commands, smoke-tested trade swarm behavior, and guarded execution backends.

### Recently validated

- [x] 60+ unit tests passing.
- [x] `src.testing.swarm_runtime_smoke` passing.
- [x] Trade heartbeat publishing fixed.
- [x] Overseer detects trade nodes through CRDT heartbeats.
- [x] Initial trade heartbeat emitted at startup.
- [x] Web3/live execution backend refuses unsafe execution when leader check fails.
- [x] Backend factory supports safe sim fallback before live adapter initialization.
- [x] `src` cleanup pass completed outside `src/swarms`.
- [x] Unused prototype modules identified for legacy quarantine.
- [x] `adapters` cleanup started.

### Current focus

- [ ] Finish `adapters/` hardening.
- [ ] Inspect and clean `sim/`.
- [ ] Continue tuning `src/swarms/trade`.
- [ ] Validate full swarm: trade + overseer + explorer + security + improver.
- [ ] Add machine-readable runtime status for dashboard.
- [ ] Build the new dashboard.

---

## 🧩 Component Map and Readiness

| Subsystem | Status | Readiness | Key artifacts |
| :--- | :--- | :--- | :--- |
| Core CRDT | Active | TRL-5 | `src/core/crdt_layer.py`, `src/core/crdt_adapter.py` |
| Event store | Active | TRL-4/5 | `src/core/event_store.py`, `src/core/events.py` |
| Gossip layer | Active | TRL-4 | `src/core/gossip_layer.py`, `src/core/gossip_adapter.py`, `src/core/gossip_filter.py` |
| Trade swarm | Active | TRL-5 | `src/swarms/trade/` |
| Overseer swarm | Active | TRL-4/5 | `src/swarms/overseer/` |
| Explorer swarm | Active | TRL-4 | `src/swarms/explorer/` |
| Security swarm | Active | TRL-3/4 | `src/swarms/security/` |
| Improver swarm | Experimental | TRL-3 | `src/swarms/improver/` |
| Trading execution | Active | TRL-4/5 | `src/trading/execution/` |
| Web3 adapter | Active testnet | TRL-5 | `adapters/web3_testnet.py` |
| Nonce manager | Active | TRL-5 | `adapters/nonce_manager.py` |
| Binance spot/futures adapters | Active testnet | TRL-4 | `adapters/live_market.py`, `adapters/futures_adapter.py` |
| Multi-pair adapter | Active | TRL-4 | `adapters/multi_pair_adapter.py` |
| TradingView webhook | Active optional | TRL-4 | `adapters/tradingview_webhook.py` |
| Order book analyzer | Active optional | TRL-4 | `adapters/orderbook_analyzer.py` |
| Simulation/evolution | Active/runtime + research | TRL-4 | `sim/`, `src/evolution/` |
| Risk layer | Active | TRL-4 | `src/risk/`, `src/swarms/trade/risk.py` |
| Memory layer | Active/prototype | TRL-3/4 | `src/memory/`, `src/intelligence/episodic_memory.py`, `src/intelligence/semantic_memory.py` |
| Formal models | Existing | TRL-4 | `formal/tla/` |
| Dashboard | Planned rebuild | TRL-2/3 | future `dashboard` runtime UI |

---

## ✅ Completed Milestones

### Core Runtime

- [x] Modular `src/swarms` runtime structure.
- [x] Trade node decomposed into context, heartbeat, trading flow, risk, maintenance, meta commands, and sync services.
- [x] CRDT-backed swarm heartbeats.
- [x] CRDT-backed swarm commands.
- [x] Shared SQLite ledgers for CRDT state.
- [x] WAL/busy-timeout database configuration.
- [x] Runtime smoke tests.
- [x] Graceful shutdown paths.

### Trade Swarm

- [x] Trade heartbeat publisher fixed.
- [x] Initial heartbeat on startup.
- [x] Periodic heartbeat publishing.
- [x] `trade_heartbeat` recognized by Overseer.
- [x] Dry-run trade path.
- [x] Execution-enabled safety gate.
- [x] Meta command application.
- [x] `SET_DRY_RUN` and `SET_EXECUTION_ENABLED` command behavior.
- [x] Deterministic leader election for live execution path.
- [x] Backend safety tests for not-leader and leader-check-failed cases.

### Trading Domain

- [x] Execution backend abstraction.
- [x] Sim execution backend.
- [x] Live/Web3 execution backend.
- [x] Backend factory with safe sim fallback before adapter initialization.
- [x] Capital manager.
- [x] Market snapshot service.
- [x] Market selector.
- [x] Swarm sync.
- [x] Mutation metrics.
- [x] Risk manager / exposure / circuit breaker pass.

### Adapters

- [x] Adapter base contract cleaned.
- [x] Futures adapter hardened.
- [x] Binance spot adapter hardened.
- [x] Multi-pair adapter hardened.
- [x] Nonce manager hardened.
- [x] Order book analyzer hardened.
- [x] TradingView webhook hardened.
- [x] Web3 Sepolia adapter hardened with slippage, result normalization, initialization alias, close path, and safer transaction flow.

### Tests

- [x] 60+ unit tests passing.
- [x] Trade execution safety tests passing.
- [x] ROI dispatcher tests passing.
- [x] Swarm runtime smoke test passing.

### Research/Architecture

- [x] Genetic engine prototype.
- [x] Survival evaluator.
- [x] Curiosity engine.
- [x] Meta-POMDP agent.
- [x] TLA+ formal models.
- [x] Multi-agent simulation.
- [x] Gold filter/data export pipeline.
- [x] Local memory prototype.

---

## 🧹 Cleanup Status

### Completed / In Progress

- [x] `src` pass completed outside `src/swarms`.
- [x] Duplicate/legacy candidates identified:
  - `src/core/crdt_state.py`
  - `src/core/d2bft.py`
  - `src/core/decision_pipeline.py`
  - `src/consensus/proposal.py`
  - `src/trading/heartbeat_publisher.py`
- [x] `src/trading/heartbeat_publisher.py` confirmed unused by runtime.
- [x] `src/core/crdt_state.py`, `d2bft.py`, `decision_pipeline.py`, and `consensus/proposal.py` confirmed unused by direct imports.
- [x] `adapters` pass started.

### Next cleanup targets

- [ ] Finish `adapters/web3_testnet.py` regression checks.
- [ ] Run full unit and smoke tests after adapter pass.
- [ ] Inspect `sim/` and classify:
  - runtime-critical modules,
  - reusable domain modules,
  - research/experiment scripts.
- [ ] Decide whether to move runtime-critical `sim` modules into `src/`.
- [ ] Inspect `src/swarms` folder in detail.

---

## 🛣️ Immediate Next Steps

### 1. Finish adapters hardening

Checklist:

- [x] `adapters/base.py`
- [x] `adapters/futures_adapter.py`
- [x] `adapters/live_market.py`
- [x] `adapters/multi_pair_adapter.py`
- [x] `adapters/nonce_manager.py`
- [x] `adapters/orderbook_analyzer.py`
- [x] `adapters/tradingview_webhook.py`
- [x] `adapters/web3_testnet.py`
- [ ] Run:

  ```bash
  python -m py_compile $(find adapters -name "*.py")
  python -m pytest -q tests/unit/core tests/unit --maxfail=1
  python -m src.testing.swarm_runtime_smoke
```

### 2. Inspect `sim/`

Current runtime imports from `sim`:

```text
sim.curiosity_engine
sim.genetic_engine
sim.meta_pomdp_agent
sim.survival_evaluator
sim.engine.environment
```

Plan:

* [ ] Review `sim/engine/environment.py`
* [ ] Review `sim/genetic_engine.py`
* [ ] Review `sim/survival_evaluator.py`
* [ ] Review `sim/curiosity_engine.py`
* [ ] Review `sim/meta_pomdp_agent.py`
* [ ] Review `sim/evolve_kelly.py`
* [ ] Review `sim/multi_agent_sim.py`
* [ ] Move or mark research-only scripts:

  * `sim/run.py`
  * `sim/sweep.py`
  * `sim/sweep_results.json`
  * `sim/scenarios/basic_economic.yaml`

### 3. Tune swarms

Trade swarm:

* [ ] Review `src/swarms/trade/trading/flow.py`.
* [ ] Make hedge execution go through guarded execution backend instead of direct adapter calls.
* [ ] Review `src/swarms/trade/node.py` for further decomposition.
* [ ] Confirm executor is rebuilt after live/web3 adapter initialization.
* [ ] Add tests for heartbeat + overseer detection.

Security swarm:

* [ ] Validate heartbeat format.
* [ ] Validate command handling.
* [ ] Ensure findings/vulnerabilities are visible to Overseer.

Explorer swarm:

* [ ] Validate heartbeat format.
* [ ] Validate safe fetch limits.
* [ ] Ensure findings are published consistently.

Improver swarm:

* [ ] Decide operational scope.
* [ ] Prevent unsafe code mutation without explicit review.
* [ ] Define dry-run/review-only mode.

Overseer:

* [ ] Normalize heartbeat collection across all swarms.
* [ ] Support `trade_heartbeat` and generic `swarm_heartbeat`.
* [ ] Add CRDT summary output for dashboard.

### 4. Add runtime status commands

Add:

```bash
python -m src.swarms.runtime.cluster_cli status --json
python -m src.swarms.runtime.cluster_cli doctor
```

`status --json` should output:

```json
{
  "run_dir": "data/cluster_runtime/latest",
  "services": [],
  "heartbeats": [],
  "trade_nodes": 0,
  "security_nodes": 0,
  "explorer_nodes": 0,
  "improver_nodes": 0,
  "overseer_nodes": 0,
  "errors": []
}
```

`doctor` should check:

* Python import path,
* writable data dirs,
* CRDT DB integrity,
* event DB integrity,
* stale pycache,
* required optional env vars,
* adapter readiness,
* port conflicts,
* dry-run/execution safety state.

### 5. Build dashboard

After `status --json` and `doctor` exist:

* [ ] Runtime overview page.
* [ ] Node cards.
* [ ] Heartbeat table.
* [ ] CRDT record browser.
* [ ] Logs viewer.
* [ ] Trade capital/fitness chart.
* [ ] Command console with safety confirmations.
* [ ] Adapter status panel.
* [ ] Test/smoke panel.
* [ ] Web3 safety panel.

---

## 🔐 Safety Roadmap

* [x] Default dry-run mode.
* [x] Explicit execution-enabled flag.
* [x] Leader-election gate.
* [x] Nonce manager.
* [x] Slippage-aware Web3 adapter path.
* [x] Private keys kept out of logs.
* [ ] Full execution approval audit trail.
* [ ] Command signing for high-risk commands.
* [ ] Per-swarm command permissions.
* [ ] Dashboard safety confirmation for live/testnet execution.
* [ ] Safer hedge path through execution backend.
* [ ] Regression tests for all live-execution blockers.

---

## 📊 Dashboard Roadmap

Dashboard should not directly depend on Docker internals. It should read from:

* `cluster_cli status --json`,
* CRDT SQLite state,
* event store,
* logs directory,
* metrics collectors.

Planned views:

1. **Overview**

   * services,
   * node status,
   * latest heartbeats,
   * errors.

2. **Trade**

   * capital,
   * fitness,
   * dry-run/execution-enabled state,
   * latest trade events.

3. **Swarms**

   * trade,
   * security,
   * explorer,
   * improver,
   * overseer.

4. **CRDT**

   * record counts,
   * heartbeat counts,
   * latest commands,
   * latest genomes.

5. **Logs**

   * tail by service,
   * filter errors/warnings,
   * download logs.

6. **Safety**

   * dry-run state,
   * execution approval,
   * private key presence indicator only,
   * adapter readiness,
   * nonce DB status.

7. **Commands**

   * safe commands,
   * TTL,
   * target selection,
   * explicit confirmation for risky commands.

---

## 🧪 Test Roadmap

Add or maintain tests for:

* [x] Trade execution safety.
* [x] ROI dispatcher.
* [x] Swarm runtime smoke.
* [ ] Adapter contracts.
* [ ] Nonce manager concurrent reservation.
* [ ] Web3 adapter dry-run/live safety.
* [ ] MultiPairAdapter initialization/close.
* [ ] TradingView webhook auth.
* [ ] OrderBookAnalyzer calculations.
* [ ] Overseer heartbeat parsing.
* [ ] `cluster_cli status --json`.
* [ ] `cluster_cli doctor`.

---

## 📦 Legacy / Experimental Modules

Current candidates for legacy quarantine:

```text
src/core/crdt_state.py
src/core/d2bft.py
src/core/decision_pipeline.py
src/consensus/proposal.py
src/trading/heartbeat_publisher.py
```

Potential future location:

```text
src/legacy/
```

Do not delete until:

* imports are checked,
* tests pass,
* runtime smoke passes,
* there is no dashboard/report dependency.

---

## 🧠 Long-Term Research Track

* Formalize command safety invariants.
* Expand TLA+ coverage for CRDT commands and execution approval.
* Improve LLM mutation evaluation with offline backtests.
* Build memory hierarchy:

  * working,
  * episodic,
  * semantic,
  * policy.
* Generate gold datasets from successful episodes.
* Add LoRA/fine-tuning experiments.
* Add self-improvement review loop for improver swarm.
* Explore Kubernetes/Helm deployment after local runtime is stable.

---

## 🗓️ Suggested Short-Term Sequence

1. Finish adapters pass.
2. Run full tests and smoke.
3. Inspect `sim`.
4. Inspect `src/swarms`.
5. Fix hedge direct execution.
6. Add `cluster_cli status --json`.
7. Add `cluster_cli doctor`.
8. Build dashboard MVP.
9. Run full swarm long-duration test.
10. Update documentation and release tag.

---

## Definition of Done for Next Internal Milestone

The next milestone is complete when:

* [ ] All unit tests pass.
* [ ] Smoke test passes.
* [ ] Full local swarm runs for 10+ minutes without unexpected service exits.
* [ ] Overseer sees all active swarms.
* [ ] Trade heartbeats are stable.
* [ ] Commands can be issued and observed through CRDT.
* [ ] Adapter pass is complete.
* [ ] `sim` classification is complete.
* [ ] Dashboard has a machine-readable status source.

---

*BlackSwan © 2026. Experimental research roadmap. Not financial advice and not a call to action.*