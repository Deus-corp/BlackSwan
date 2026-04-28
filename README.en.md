# Black Swan

**Autonomous, self-improving AI system with defense in depth, a distributed swarm, economic sovereignty, and a continuous operational security loop.**

[![Status](https://img.shields.io/badge/status-prototype%20(TRL--3)-yellow)](#)
[![Version](https://img.shields.io/badge/version-2.2%20DarkSwan-darkgreen)](#)
[![License](https://img.shields.io/badge/license-MIT%2FApache%202.0-yellow)](#)
[![CI](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](#)

> [!CAUTION]
> This project describes hypothetical protocols (Omega, Last Breath, Sting). Their physical implementation is illegal and strongly discouraged.

---

## 🎯 Project Status

| Level | Definition | Status |
| :--- | :--- | :--- |
| **TRL-3** | Experimental demonstration of key functions | ✅ Current status |

**What already works:**
- Closed economic cycle MVP (`mvp/cycle_demo.py`) with isolated sandbox (Docker).
- Bayesian `ROIDispatcher` (Kelly criterion) demonstrated Sharpe > 0 and lower drawdown than a random agent.
- Unit tests for the core (`GlobalState`, `EventBus`, `ROIDispatcher`, `IPFSClient`) and CI/CD (pytest in GitHub Actions).
- Formal verification of node lifecycle (`NodeLifecycle.tla`) with automatic TLC checks.
- Economic swarm simulator (`sim/`) with configurable scenarios.

---

## 📁 Repository Structure
BlackSwan/
- .github/workflows/ – CI/CD
- docs/
  - architecture/ – core system
  - deployment/ – launch
  - domains/ – domain modules
  - singularity/ – final protocols
  - appendices/ – technical appendices
  - adr/ – architecture decision records
  - development/ – developer guides
- formal/ – formal specifications (TLA+)
- sim/ – economic swarm simulator
- mvp/ – minimum viable prototype (TRL-3)
- src/ – source code (core)
- tests/ – unit tests
- config/ – reference configuration files


---

## 🚀 Quick Start

```bash
# Install dependencies
pip install numpy requests

# Run the demo cycle
python mvp/cycle_demo.py

# Run tests
PYTHONPATH=. pytest tests/ -v
Documentation: start with docs/README.md.

📜 License
MIT / Apache 2.0.