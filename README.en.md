# BlackSwan 🦢

**Autonomous, self‑healing AI swarm with defense‑in‑depth and economic sovereignty.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)

---

## 📌 Project Status: **TRL-4** (laboratory‑validated components)

- ✅ Formal TLA+ specs (`NodeLifecycle`, `D2BFT`, `GlobalState`, `SporeProtocol`)
- ✅ Economic simulator with multi‑agent parameter sweep
- ✅ Docker swarm lab demo (8 nodes, Redis pub/sub, auto‑recovery)
- ✅ CI/CD: unit tests, nightly simulation runs
- 📖 [Full TRL-4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- 🗺 [Roadmap](ROADMAP.md)

---

## 🧬 Key Features

- **Self‑Sovereign Economy** – built‑in market and Kelly‑criterion capital dispatcher.
- **Defense in Depth** – multi‑layer isolation, traffic obfuscation, formally verified survival protocols.
- **Swarm Resilience** – automatic failure detection and Spore Protocol (node rebirth).
- **Formally Verified Core** – critical properties proven in TLA+.

---

## 🚀 Quick Start (local demo)

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
python mvp/cycle_demo.py          # single agent
python sim/multi_agent_sim.py     # multi‑agent run
python sim/sweep.py               # stability zone search
🐳 Docker Swarm (TRL-4)
bash
docker compose -f mvp/lab_swarm_demo/docker-compose.yml up --build -d
# Node logs
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs -f node
📚 Documentation
Architecture decisions

Formal verification

Simulation report

TRL-4 Validation

📄 License
Dual‑licensed under MIT or Apache‑2.0, at your option.
See LICENSE-MIT and LICENSE-APACHE.