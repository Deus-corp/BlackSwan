# BlackSwan 🦢

**Autonomous, self‑improving AI swarm with distributed evolution, economic sovereignty, and formally verified core.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)

---

## 📌 Project Status: **TRL-4** (laboratory‑validated components)

- ✅ Formal TLA+ specs (`NodeLifecycle`, `D2BFT`, `GlobalState`, `SporeProtocol`, `Ouroboros`)
- ✅ Economic simulator with multi‑agent sweep and stability zone discovery
- ✅ Docker lab swarm (8 nodes, Redis pub/sub, auto‑recovery)
- ✅ **Ouroboros v0.2** — distributed strategy evolution, genome exchange between nodes
- ✅ CI/CD: unit tests, formal verification (local + GitHub Actions)
- 📖 [Full TRL-4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- 📖 [Ouroboros TRL-4 Report](docs/TRL4_OUROBOROS_REPORT.md)
- 🗺 [Roadmap](ROADMAP.md)

---

## 🧬 Key Features

- **Self‑Sovereign Economy** – built‑in market and Kelly‑criterion capital dispatcher.
- **Defense in Depth** – multi‑layer isolation, traffic obfuscation, formally verified survival protocols.
- **Swarm Resilience** – automatic failure detection and Spore Protocol (node rebirth).
- **Ouroboros Self‑Improvement** – genetic search for optimal strategies, genome exchange in the swarm.
- **Formally Verified Core** – critical invariants proven in TLA+.

---

## 🚀 Quick Start (local demo)

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
python mvp/cycle_demo.py          # single agent
python sim/multi_agent_sim.py     # multi‑agent run
python sim/evolve_kelly.py        # evolve Kelly params (Ouroboros)
```

## 🐳 Docker Swarm (TRL-4)
```bash
docker compose -f mvp/lab_swarm_demo/docker-compose.yml up --build -d
# Node logs
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs -f node
```
## 📚 Documentation

- [Architecture decisions](docs/architecture/)
- [Formal verification](formal/tla/)
- [Simulation report](docs/TRL4_simulation_baseline.md)
- [TRL-4 Validation](docs/TRL4_VALIDATION_REPORT.md)
- [Ouroboros Report](docs/TRL4_OUROBOROS_REPORT.md)

---

## 📄 License

Dual‑licensed under MIT or Apache‑2.0, at your option.  
See [LICENSE-MIT](LICENSE-MIT.md) and [LICENSE-APACHE](LICENSE-APACHE.md).

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*