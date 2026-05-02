# BlackSwan 🦢

**Autonomous, self‑improving AI swarm with distributed evolution, economic sovereignty, and formally verified core.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)

---

## 📌 Project Status: **TRL‑4** (laboratory‑validated components)

- ✅ Formal TLA+ specifications for 8 protocols (including Ouroboros, SurvivalObjective, GeneticEngine, CuriosityEngine, AdaptiveMotivation)
- ✅ Economic simulator with multi‑agent sweep and stability zone discovery
- ✅ Docker lab swarm (8 nodes, Redis pub/sub, auto‑recovery)
- ✅ **Ouroboros v0.3** — distributed strategy evolution with Champion/Challenger and L2 memory
- ✅ **SurvivalObjective** — intelligent rejection of dangerous trades
- ✅ **GeneticEngine** — full population‑based evolution with formal verification
- ✅ **Adaptive Intrinsic Motivation** — Meta‑POMDP agent switches between 5 scenarios based on market conditions
- ✅ **Curiosity Engine** — proactive exploration of market anomalies
- ✅ Prototypes of **CRDT state** and **D2BFT consensus**
- 🧪 **Decentralized Gossip** — async CRDT‑gossip genome exchange (feature branch)
- ✅ CI/CD: unit tests, formal verification (local + GitHub Actions)
- 📖 [Documentation site](https://deus-corp.github.io/BlackSwan/)
- 📖 [Full TRL‑4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- 🗺 [Roadmap](ROADMAP.md)
- 🏭 **Industrial CRDT** – SQLite-backed, op-based CRDT with deterministic LWW merge.
- 🛡️ **Secure Gossip** – HMAC-signed envelopes, replay protection, peer scoring and backoff.
- 🧬 **Speciated Genetic Engine** – species-based evolution with adaptive mutation and fitness cache.
- 🧠 **LLM-Powered Mutations** – a local LLM (Qwen2.5-1.5B) generates new strategy parameters instead of random mutations.
- ✅ **Multinode DeepSeek Swarm** — 4–5 nodes on DeepSeek-R1-Distill-Qwen-1.5B, shared read‑only model volume, resource limits for low‑RAM PCs (v2.13)
- ✅ **Multi-model benchmark** – 10 local LLMs compared (135M–1.7B). Report: [docs/reports/benchmark_10_models_2026-05-03.md](docs/reports/benchmark_10_models_2026-05-03.md)

---

## 🧬 Key Features

- **Self‑Sovereign Economy** – built‑in market and Kelly‑criterion capital dispatcher.
- **Ouroboros Self‑Improvement** – genetic search for optimal strategies, genome exchange in the swarm, Champion/Challenger.
- **Survival Objective** – each node evaluates detection risk and refuses dangerous actions.
- **Adaptive Intrinsic Motivation** – dynamic balancing of capital, stealth, and curiosity via Meta‑POMDP.
- **Curiosity Engine** – autonomous detection of market anomalies and generation of research hypotheses.
- **Swarm Resilience** – automatic failure detection and Spore Protocol (node rebirth).
- **Formally Verified Core** – critical invariants proven in TLA+.
- **Defense in Depth** – multi‑layer isolation, traffic obfuscation.

---

## 🚀 Quick Start (local demo)

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
python mvp/cycle_demo.py          # single agent
python sim/multi_agent_sim.py     # multi‑agent run
python sim/evolve_kelly.py        # evolve Kelly params
python sim/genetic_engine.py      # full Genetic Engine
python sim/survival_evaluator.py  # test survival logic
python sim/meta_pomdp_agent.py    # test adaptive motivation
```

## 🐳 Docker Swarm (TRL‑4)
```bash
docker compose -f mvp/lab_swarm_demo/docker-compose.yml up --build -d
# Node logs
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs -f node
```

## 🧪 Model Benchmark
python model_benchmark.py   # автоматически прогонит все модели и сохранит логи в docs/logs/models/

## 📚 Documentation

- [Documentation site](https://deus-corp.github.io/BlackSwan/)
- [Architecture decisions](docs/architecture/)
- [Formal verification](formal/tla/)
- [Simulation report](docs/TRL4_simulation_baseline.md)
- [TRL‑4 Validation](docs/TRL4_VALIDATION_REPORT.md)
- [Ouroboros Report](docs/TRL4_OUROBOROS_REPORT.md)

---

## 📄 License

Dual‑licensed under MIT or Apache‑2.0, at your option.  
See [LICENSE-MIT](LICENSE-MIT.md) and [LICENSE-APACHE](LICENSE-APACHE.md).

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*