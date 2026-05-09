# Black Swan — Roadmap

**Purpose:** Single source of truth about project progress. Shows which components are already implemented, which are in active development, and how the project moves from a laboratory prototype (TRL‑4) towards a fully autonomous, self‑improving system (TRL‑7+).

---

## 🔭 Vision

Create a distributed AI swarm capable of autonomously surviving, self‑healing, earning resources, and continuously improving its own code without violating fundamental safety axioms (L3.0).

---

## 📍 Current Status (May 2026)

**Overall readiness level: TRL‑5 (laboratory‑validated system with real on‑chain execution)**

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
✅ **Multi‑model benchmark completed** – 10 models evaluated, top performer: SmolLM2-1.7B-Instruct (fitness 0.898).  
✅ Spore protocol stress‑test completed (4 nodes, high failure rate, automatic recovery).  
✅ Signed GossipEnvelope implemented – genome exchange cryptographically signed.  
✅ Signed genome exchange with Ed25519 verified and tested in live swarm.  
🔑 Key Manager now centralizes all private keys; keys are never exposed in logs.  
📜 Intelligence Contract v1.0 defines strict boundaries between Infrastructure and Intelligence layers.  
📊 Gold Filter pipeline extracts successful trading episodes into JSONL datasets for future LoRA training.  
✅ Binance Futures adapter with stop‑loss and dynamic leverage.  
✅ Spot/Futures hedging for risk mitigation.  
✅ Order Book analysis and TradingView webhooks.  
✅ Web Control Panel for full swarm management.  
✅ **Web3 Testnet Adapter** – Uniswap V3 integration on Ethereum Sepolia, real AI‑driven swaps executed.  
✅ **Autonomous Token Management** – auto‑wrap ETH, auto‑convert USDC↔WETH based on configurable thresholds.  
✅ **Multi‑node Nonce Synchronization** – SQLite‑based coordination for conflict‑free parallel swaps.
✅ **Prometheus + Grafana integration** – professional metrics & dashboards  
✅ **Embedded Grafana dashboard** in Web Control Panel  
✅ **Settings page** for all compose variables and secrets  

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

- **Build metrics dashboard** – visualise capital, fitness, diversity, and gossip health (Prometheus + Grafana).
- **Harden gossip security** – add Ed25519 signatures, peer reputation, and optional TLS.
- **Evaluate Kubernetes deployment** – prepare Helm chart for production‑grade swarm.
- Activate `GOSSIP_SIGNING_ENABLED=true` and verify signed genome exchange without failures.
- Begin design of LocalMemoryAPI (working/episodic/semantic/policy layers).
- Prepare adapter for Binance Testnet (CCXT integration).
- Validate gold‑filter output with real profitable episodes; prepare first fine‑tuning dataset.
- Compare single‑pair vs multi‑pair strategy performance over long runs.
- Add Prometheus/Grafana dashboards for live metrics.

---

*Black Swan © 2026. All plans are hypothetical and do not constitute a call to action.*