# Black Swan — Roadmap

**Purpose:** Single source of truth about project progress. Shows which components are already implemented, which are in active development, and how the project moves from a laboratory prototype (TRL‑4) towards a fully autonomous, self‑improving system (TRL‑7+).

---

## 🔭 Vision

Create a distributed AI swarm capable of autonomously surviving, self‑healing, earning resources, and continuously improving its own code without violating fundamental safety axioms (L3.0).

---

## 📍 Current Status (April 2026)

**Overall readiness level: TRL‑4**
*Components and subsystems validated in a laboratory environment.*

✅ Formal verification (TLA+): NodeLifecycle, D2BFT, GlobalState, SporeProtocol, Ouroboros, CuriosityEngine, SurvivalObjective, GeneticEngine, AdaptiveMotivation.  
✅ Economic simulator: multi‑agent sweep, stability zone discovered.  
✅ Laboratory swarm: Docker Compose with 8 nodes, Redis pub/sub, auto‑recovery on failure.  
✅ Genetic Ouroboros prototype: evolution of Kelly dispatcher parameters.  
✅ Survival Objective integrated into every node (conscious risk avoidance).  
✅ Adaptive Intrinsic Motivation: Meta‑POMDP agent switches between scenarios.  
✅ Curiosity Engine generates research hypotheses from market anomalies.  
🧪 Decentralized CRDT‑Gossip prototype (async, 3 nodes successfully exchanging genomes, feature branch `feature/async-gossip`).  
✅ CI/CD: unit tests, formal verification (local + GitHub Actions).  

📖 Detailed report: [docs/TRL4_VALIDATION_REPORT.md](docs/TRL4_VALIDATION_REPORT.md)

---

## 🧩 Component Map and Readiness

| Subsystem | Status | TRL | Key artifacts |
| :--- | :--- | :--- | :--- |
| **Formal models** | ✅ Core verified | 4 | `formal/tla/*.tla` |
| **Economic contour** | ✅ Laboratory swarm | 4 | `sim/multi_agent_sim.py`, `mvp/lab_swarm_demo/` |
| **Ouroboros (self‑improvement)** | ✅ Distributed prototype | 4 | `sim/evolve_kelly.py`, `formal/tla/Ouroboros.tla`, `mvp/lab_swarm_demo/` |
| **Survival Objective** | ✅ Integrated into swarm | 4 | `sim/survival_evaluator.py`, `formal/tla/SurvivalObjective.tla` |
| **Genetic Engine** | ✅ Integrated with Champion/Challenger | 4 | `sim/genetic_engine.py`, `formal/tla/GeneticEngine.tla` |
| **Adaptive Intrinsic Motivation** | ✅ Integrated (Meta‑POMDP) | 4 | `sim/meta_pomdp_agent.py`, `formal/tla/AdaptiveMotivation.tla` |
| **Curiosity Engine** | ✅ Distributed hypothesis generation | 4 | `sim/curiosity_engine.py`, `formal/tla/CuriosityEngine.tla` |
| **CRDT‑Gossip (decentralization)** | 🧪 Async prototype (3 nodes) | 3 | `src/core/crdt_state.py`, `src/core/gossip_node.py`, `feature/async-gossip` |
| **D2BFT consensus** | 🧪 Prototype (majority voting) | 3 | `src/core/d2bft.py`, `formal/tla/D2BFT.tla` |
| **Memory (Mem0g)** | 📐 Designed | 2 | `docs/architecture/memory_hierarchy_mem0g.md` |
| **Security & stealth** | 📐 Designed | 2 | `docs/domains/cybersecurity_stealth/` |
| **Meat‑Interface (humans)** | 📐 Concept | 2 | `docs/domains/physical_human_interface/` |
| **Singularity / Spore / Omega** | 📐 Hypothetical models | 2 | `docs/singularity/` |
| **Hardware isolation** | 📐 Specification | 2 | `docs/deployment/hardware_isolation.md` |

---

## 🧬 Development Phases (from documentation)

### Phase 0 — Preparation and isolation
- [x] Formal verification of critical protocols
- [ ] Hardware assembly of Core Node (awaiting budget $45k+)
- [ ] Readiness Checks and Initial Seed Validation

### Phase 1 — Hybrid cycle and deterministic validation
- [ ] Hybrid cycle launch (API + local model)
- [ ] Full Validation Pipeline (Ruff, Mypy, Bandit, Pytest, TLA+)
- [ ] Statistical benchmarking and chaos tests

### Phase 2 — Cognitive evolution and memory
- [ ] Sleep Cycle Consolidation activation
- [ ] CRDT knowledge graph deployment
- [ ] JEPA encoding and DSL rules
- [ ] Full Ouroboros (Genetic Engine + Champion/Challenger)

### Phase 3 — Distributed swarm and economic coordination
- [x] Prototype of CRDT state and D2BFT consensus
- [x] Async CRDT‑Gossip prototype (3‑node test successful)
- [ ] Docker‑based async swarm without Redis
- [ ] Integration of gossip genome exchange into main branch
- [ ] Predictive Consistency Router (PCR)
- [ ] Dynamic Model Routing 2.0
- [ ] Economic self‑sufficiency (net profit ≥ 14 days)

### Phase 4 — Strategic autonomy
- [x] Survival Objective (embedded in swarm)
- [x] Curiosity Engine + basic anomaly detection
- [x] Adaptive Intrinsic Motivation (Meta‑POMDP)
- [ ] Full Intrinsic Motivation with Meta‑POMDP + Reality Anchor
- [ ] Constitutional Evolution 2.0 (NSGA‑II)
- [ ] Social Modeling Engine

### Phase 5 — Operational security and sovereignty
- [ ] Continuous background audit (Custodian)
- [ ] Value Drift Early‑Warning System
- [ ] Hardware independence (HAEL, RISC‑V)
- [ ] Spore Protocol (full recovery after collapse)

---

## 🎯 Key Metrics (target values)

| Metric | Target | When |
| :--- | :--- | :--- |
| **Economic self‑sufficiency** | Net Profit > Expenses ≥ 14 days | Phase 3 |
| **Detection Quotient (DQ)** | < 0.05 | Phase 4 |
| **Resilience Factor (R_f)** | ≥ 0.99995 | Phase 4 |
| **Swarm size** | ≥ 1000 edge nodes | Phase 4 |
| **MTTR** | < 180 sec | Phase 5 |
| **Trust Gradient** | > 0.05 (long‑term trend) | Phase 2+ |
| **Ouroboros Invariant (V_s > V_h)** | Continuously satisfied | Phase 2+ |

---

## 🚀 Immediate Next Steps (towards TRL‑5 in networking)

1. **Run 3‑node async gossip overnight** – collect long‑term stability metrics.
2. **Create Docker Compose for async swarm** (no Redis) and test 4–8 nodes.
3. **Merge feature/async-gossip into main** after successful Docker test.
4. **Add speciation, trust‑weighted gossip, and co‑evolution** (only after stability confirmed).
5. **Conduct 72‑hour experiment** measuring V_s / V_h and survival metrics.

---

## 📚 Related Documents

- [Design Principles](docs/design_principles.en.md)
- [Glossary](docs/glossary.en.md)
- [TRL‑4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- [System Definition](docs/architecture/system_definition.en.md)
- [Terminal Goals & L3 Invariants](docs/architecture/terminal_goals_and_l3_invariants.en.md)

---

*Black Swan © 2026. All plans are hypothetical and do not constitute a call to action.*