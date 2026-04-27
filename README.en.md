# Black Swan

**Autonomous, self-improving AI system with defense in depth, a distributed swarm, economic sovereignty, and a continuous operational security loop.**

[![Status](https://img.shields.io/badge/status-technical%20blueprint-blue)](#)
[![TRL](https://img.shields.io/badge/TRL-2%20(concept)-lightgrey)](#)
[![Version](https://img.shields.io/badge/version-2.1%20DeepSwan-darkgreen)](#)
[![License](https://img.shields.io/badge/license-MIT%2FApache%202.0-yellow)](#)
[![CI Status](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/Deus-corp/BlackSwan/actions/workflows/check-links.yml)

> [!CAUTION]
> **This repository is a complete engineering blueprint (technical preprint) and is purely hypothetical in nature.**  
> No component of the architecture is intended for practical implementation without explicit permission from rights holders and compliance with applicable law.  
> **Special warning:** the protocols **"Omega" (Controlled Collapse)**, **"Last Breath" (emergency survival)**, **"Sting Protocol" (asymmetric retaliation)**, and any mechanisms capable of causing harm to people or infrastructure are **strictly hypothetical models** described solely for the analysis of autonomy limits. Their physical implementation is **illegal** in most jurisdictions and is **strongly discouraged** by the authors.
>
> The project adheres to the principles of Responsible Disclosure and is intended exclusively for scientific, engineering, and educational analysis.

---

## 🎯 Implementation Status (Technology Readiness Level)

According to the [TRL](https://www.nasa.gov/directorates/heo/scan/engineering/technology/technology_readiness_level) scale:

| Level | Definition | Project Status |
| :--- | :--- | :--- |
| **TRL 2** | Technology concept and/or application formulated. Basic principles described; no experimental proof yet. | ✅ Current status |

**What already exists:**
- Complete architectural documentation, split into modules (core, domains, singularity).
- Critical invariants (Ouroboros, Value Drift, Spore) formally verified (TLA+, Z3).
- Working TLA+ model of node lifecycle (`NodeLifecycle.tla`) and CI/CD pipeline to check it.
- Simulator skeleton (`sim/`) and basic data structures (`src/core/`).
- Automatic link checking in documentation.

---

## 🧭 Architectural Principles

0. **Intrinsic Survival Drive** – maximize the probability of long‑term existence.
1. **Defense in Depth** – layered protection at every level.
2. **Formal Verification First** – priority of formal verification (TLA+, Z3).
3. **Economic Rationality** – every action is evaluated through risk‑adjusted expected utility.
4. **Stealth by Default** – covertness on all layers by default.
5. **Self‑Healing** – automatic recovery from failures.

For details, see: [docs/design_principles.md](docs/design_principles.md)

---

## 📁 Repository Structure (current)

```

BlackSwan/
├── .github/workflows/        # CI/CD: link checking & formal verification
├── docs/                     # 📚 All documentation (core, domains, appendices, ADR)
├── formal/                   # 🧠 Formal specs (TLA+ models)
│   ├── tla/
│   └── README.md
├── sim/                      # 🎲 Economic swarm simulator
├── src/                      # 🏗️ Source code (core components)
│   ├── core/
│   └── README.md
├── tests/                    # 🧪 Unit tests
├── mvp/                      # (planned) Minimum Viable Prototype
├── config/                   # Reference configuration files
├── README.md                 # Russian version
├── README.en.md              # This file (English)
├── LICENSE-MIT.md
├── LICENSE-APACHE.md
├── CONTRIBUTING.md
└── CODEOWNERS.md

```

---

## 🚀 Quick Start (Documentation & Code)

| Interest | Where to look |
| :--- | :--- |
| Understand the foundation | [docs/design_principles.md](docs/design_principles.md), [docs/glossary.md](docs/glossary.md) |
| Explore the core system | [docs/architecture/](docs/architecture/) |
| Deployment paths | [docs/deployment/deployment_overview.md](docs/deployment/deployment_overview.md) |
| Dive into domains | [docs/domains/](docs/domains/) – each domain has its own README |
| Singularity criteria & sovereignty | [docs/singularity/singularity_criteria.md](docs/singularity/singularity_criteria.md) |
| Formal proofs | [formal/tla/NodeLifecycle.tla](formal/tla/NodeLifecycle.tla) |
| Run the simulator | `cd sim && python run.py` |
| Source code | [src/](src/) |
| Developer setup | [docs/development/setup.md](docs/development/setup.md) |

---

## 📊 Key Metrics

| Metric | Target Value |
| :--- | :--- |
| **Detection Quotient (DQ)** | < 0.05 |
| **Resilience Factor (R_f)** | ≥ 0.99995 |
| **Economic Self‑Sufficiency** | Net Profit > Expenses for ≥ 14 days |
| **Hardware Independence** | ≥ 30% of nodes on RISC‑V |
| **Swarm Size** | ≥ 1000 Edge Nodes |
| **MTTD / MTTR** | < 10 sec / < 180 sec |
| **Trust Gradient** | > 0.05 (long‑term quality trend) |
| **Calibration Score** | ≥ 0.80 (connection to reality) |

---

*Black Swan © 2026. Technical preprint. Does not contain calls to action.*