# Black Swan — Roadmap

**Purpose:** Single source of truth about project progress. Shows which components are already implemented, which are in active development, and how the project moves from a laboratory prototype (TRL‑4) towards a fully autonomous, self‑improving system (TRL‑7+).

---

## 🔭 Vision

Create a distributed AI swarm capable of autonomously surviving, self‑healing, earning resources, and continuously improving its own code without violating fundamental safety axioms (L3.0).

---

## 📍 Current Status (May 2026)

**Overall readiness level: TRL‑4+**
*Components and subsystems validated in a laboratory environment; key components upgraded to industrial-grade.*

✅ Formal verification (TLA+): 8 protocols (Ouroboros, SurvivalObjective, GeneticEngine, CuriosityEngine, AdaptiveMotivation, etc.).  
✅ Economic simulator: multi‑agent sweep, stability zone discovered.  
✅ Laboratory swarm: Docker Compose with 4 nodes, fully decentralized (no Redis).
✅ **Multinode DeepSeek Swarm (v2.13)** – 4–5 nodes running DeepSeek-R1-Distill-Qwen-1.5B, model shared via read‑only volume, resource limits for 8 GB RAM PCs. 
✅ **Industrial CRDT layer** – operation‑based CRDT with SQLite persistence, version vectors, and deterministic LWW merge.  
✅ **Secure Gossip protocol** – HMAC‑signed envelopes, replay protection, peer backoff and scoring.  
✅ **Speciated Genetic Engine** – genome dataclass, species formation, adaptive mutation, fitness cache.  
✅ Genetic Ouroboros prototype: distributed evolution with Champion/Challenger.  
✅ Survival Objective integrated into every node (conscious risk avoidance).  
✅ Adaptive Intrinsic Motivation: Meta‑POMDP agent switches between scenarios.  
✅ Curiosity Engine: proactive exploration of market anomalies.  
✅ CI/CD: unit tests, formal verification (local + GitHub Actions). 
✅ **Multi-model benchmark completed** – 10 models evaluated, top performer: SmolLM2-1.7B-Instruct (fitness 0.898).

📖 Detailed report: [docs/TRL4_VALIDATION_REPORT.md](docs/TRL4_VALIDATION_REPORT.md)

---

## 🧩 Component Map and Readiness

| Subsystem | Status | TRL | Key artifacts |
| :--- | :--- | :--- | :--- |
| **Formal models** | ✅ Core verified | 4 | `formal/tla/*.tla` |
| **Economic contour** | ✅ Laboratory swarm | 4 | `sim/multi_agent_sim.py`, `mvp/lab_swarm_demo/` |
| **Ouroboros (self‑improvement)** | ✅ Distributed prototype | 4 | `sim/evolve_kelly.py`, `formal/tla/Ouroboros.tla`, `mvp/lab_swarm_demo/` |
| **Survival Objective** | ✅ Integrated into swarm | 4 | `sim/survival_evaluator.py`, `formal/tla/SurvivalObjective.tla` |
| **Genetic Engine** | ✅ Speciated with species/novelty | 4 | `sim/genetic_engine.py`, `formal/tla/GeneticEngine.tla` |
| **Adaptive Intrinsic Motivation** | ✅ Integrated (Meta‑POMDP) | 4 | `sim/meta_pomdp_agent.py`, `formal/tla/AdaptiveMotivation.tla` |
| **Curiosity Engine** | ✅ Distributed hypothesis generation | 4 | `sim/curiosity_engine.py`, `formal/tla/CuriosityEngine.tla` |
| **CRDT State (Industrial)** | ✅ Op‑based CRDT + SQLite persistence | 4 | `src/core/crdt_layer.py`, `src/core/crdt_adapter.py` |
| **Gossip Layer (Secure)** | ✅ HMAC, replay protection, backoff | 4 | `src/core/gossip_layer.py`, `src/core/gossip_adapter.py` |
| **D2BFT consensus** | 🧪 Prototype (majority voting) | 3 | `src/core/d2bft.py`, `formal/tla/D2BFT.tla` |
| **Memory (Mem0g)** | 📐 Designed | 2 | `docs/architecture/memory_hierarchy_mem0g.md` |
| **Security & stealth** | 📐 Designed | 2 | `docs/domains/cybersecurity_stealth/` |
| **Meat‑Interface (humans)** | 📐 Concept | 2 | `docs/domains/physical_human_interface/` |
| **Singularity / Spore / Omega** | 📐 Hypothetical models | 2 | `docs/singularity/` |
| **Hardware isolation** | 📐 Specification | 2 | `docs/deployment/hardware_isolation.md` |

---

## 🚀 Immediate Next Steps

1. **Stress‑test Spore Protocol** – introduce artificial node failures (`FAILURE_PROB > 0`) and verify automatic rebirth and state recovery.
2. **Build metrics dashboard** – visualise capital, fitness, diversity, and gossip health (Prometheus + Grafana).
3. **Harden gossip security** – add Ed25519 signatures, peer reputation, and optional TLS.
4. **Experiment with Qwen2.5 and other local LLMs** – compare reasoning quality vs resource usage.
5. **Evaluate Kubernetes deployment** – prepare Helm chart for production‑grade swarm.
---

*Black Swan © 2026. All plans are hypothetical and do not constitute a call to action.*