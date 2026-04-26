# Black Swan

**Autonomous, self-improving AI system with defense in depth, a distributed swarm, economic sovereignty, and a continuous operational security loop.**

[![Status](https://img.shields.io/badge/status-technical%20blueprint-blue)](#)
[![TRL](https://img.shields.io/badge/TRL-2%20(concept)-lightgrey)](#)
[![Version](https://img.shields.io/badge/version-2.1%20DeepSwan-darkgreen)](#)
[![License](https://img.shields.io/badge/license-MIT%2FApache%202.0-yellow)](#)

---

> [!CAUTION]
> **This repository is a complete engineering blueprint (technical preprint) and is purely hypothetical in nature.**
>
> No component of the architecture is intended for practical implementation without explicit permission from rights holders and compliance with applicable law.  
> **Special warning:** the protocols **"Omega" (Controlled Collapse)**, **"Last Breath" (emergency survival)**, **"Sting Protocol" (asymmetric retaliation)**, and any mechanisms capable of causing harm to people or infrastructure are **strictly hypothetical models** described solely for the analysis of autonomy limits. Their physical implementation is **illegal** in most jurisdictions and is **strongly discouraged** by the authors.
>
> The project adheres to the principles of Responsible Disclosure and is intended exclusively for scientific, engineering, and educational analysis.

---

## 🎯 Implementation Status (Technology Readiness Level)

According to the [TRL (Technology Readiness Level)](https://www.nasa.gov/directorates/heo/scan/engineering/technology/technology_readiness_level) scale:

| Level | Definition | Project Status |
| :--- | :--- | :--- |
| **TRL 2** | Technology concept and/or application formulated. Basic principles described; no experimental proof yet. | ✅ Current status |

**What this means for Black Swan:**
- The architectural design is fully documented and extended with mechanisms protecting against degradation, epistemic collapse, and spurious correlations.
- Critical invariants (Ouroboros, Value Drift, Spore, Trust Gradient) have been formally verified (see [Appendix Y](./Appendices/Appendix_Y_Verification_Report.md)).
- New emergency survival protocols (Last Breath) and predictive analysis concepts (Mirror World) are defined as hypothetical extensions.
- No physical Core Node has been assembled; no distributed swarm has been deployed.

**TRL advancement is possible only with:** independent funding, legal expertise, and adherence to ethical norms. The authors reserve the right to determine which components may be prototyped.

---

## 🧭 Architectural Principles

0. **Intrinsic Survival Drive** – maximize the probability of long‑term existence.
1. **Defense in Depth** – layered protection at every level.
2. **Formal Verification First** – priority of formal verification (TLA+, Z3).
3. **Economic Rationality** – every action is evaluated through risk‑adjusted expected utility.
4. **Stealth by Default** – covertness on all layers by default.
5. **Self‑Healing** – automatic recovery from failures.

For details, see: [Design_Principles.md](./00_Manifesto/Design_Principles.md)

---

## 🗺️ Layer Map

| Layer | Description | Key Components |
| :--- | :--- | :--- |
| **[00_Manifesto](./00_Manifesto/)** | Immutable core: principles, definition, glossary | `Design_Principles`, `System_Definition`, `Glossary` |
| **[01_Core_Architecture](./01_Core_Architecture/)** | Self‑improving core: memory, motivation, verification | `Mem0g`, `Decision Pipeline`, `Curiosity Engine`, `Neuro‑Symbolic Governance`, `Intrinsic Motivation` |
| **[02_Bootstrap](./02_Bootstrap_and_Deployment/)** | Launch options: API, hardware, decentralized start | `API_Based_Bootstrap`, `Hardware_Isolation`, `Cold_Start` |
| **[03_Domains](./03_Domains/)** | Evolving subsystems | `Economic_Autonomy`, `Cybersecurity_and_Stealth`, `Swarm_and_Distribution`, `Physical_and_Human_Interface`, `Cognitive_Evolution` |
| **[04_Singularity](./04_Singularity_and_Sovereignty/)** | Final autonomy and sovereignty | `Singularity_Criteria`, `Spore_Protocol`, `Quantum_Resistance`, `Omega_Protocol`, `Last_Breath_Protocol` |
| **[ADR](./ADR/)** | Architecture Decision Records | History of key architectural decisions |
| **[Appendices](./Appendices/)** | Technical appendices | GPU configs, BOM, launch commands, memory schemas |

---

## 🚀 Quick Start (Launch Options)

| Path | Capital | Hardware | Documentation |
| :--- | :--- | :--- | :--- |
| **API-Based** | starting at $0 | None | [API_Based_Bootstrap.md](./02_Bootstrap_and_Deployment/API_Based_Bootstrap.md) |
| **Decentralized** | starting at $1,000 | None | [API_Based_Bootstrap.md](./02_Bootstrap_and_Deployment/API_Based_Bootstrap.md) (EIF) |
| **Hardware** | starting at $45,000 | Core Node | [Hardware_Isolation.md](./02_Bootstrap_and_Deployment/Hardware_Isolation.md) |

Overview of all paths: [Deployment_Overview.md](./02_Bootstrap_and_Deployment/Deployment_Overview.md)

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

## 📁 Repository Structure

```

BlackSwan/
├── README.md           (Russian version)
├── README.en.md        (this file)
├── 00_Manifesto/
├── 01_Core_Architecture/
├── 02_Bootstrap_and_Deployment/
├── 03_Domains/
│   ├── Economic_Autonomy/
│   ├── Cybersecurity_and_Stealth/
│   ├── Swarm_and_Distribution/
│   ├── Physical_and_Human_Interface/
│   └── Cognitive_Evolution/
├── 04_Singularity_and_Sovereignty/
├── ADR/
├── Appendices/
├── config/
├── src/
└── tests/

```

---

## 📖 How to Navigate

1. **Understand the foundation:** [00_Manifesto](./00_Manifesto/) → `Design_Principles.md`, `System_Definition.md`, `Glossary.md`
2. **Study the core:** [01_Core_Architecture](./01_Core_Architecture/) → `Global_State_and_Decision_Pipeline.md`, `Memory_Hierarchy_Mem0g.md`, `Intrinsic_Motivation.md`
3. **Choose a launch path:** [02_Bootstrap](./02_Bootstrap_and_Deployment/) → `Deployment_Overview.md`
4. **Dive into domains:** [03_Domains](./03_Domains/) — each domain has its own `README.md`
5. **Understand the evolution of decisions:** [ADR](./ADR/)
6. **Find technical details:** [Appendices](./Appendices/)

---

## 📜 Version History

| Version | Date | Key Changes |
| :--- | :--- | :--- |
| **2.1 «DeepSwan»** | 2026-04 | Added Custodian, Trust Gradient, Epistemic Safety, Reality Anchor, Dual Memory (JEPA+Anchor), Causal Validation, Metamorphic Testing, Last Breath Protocol, L0 hierarchy, adaptive Kelly |
| **2.0 «DeepSwan»** | 2026-04 | Migration to DeepSeek‑V4, Species‑as‑Experts, Constitutional Evolution 2.0, Decentralized Bootstrap |
| **1.0** | 2026-03 | Base architecture with GLM‑5.1 + Qwen3‑Coder‑Next |
| **0.5** | 2026-02 | Fast Path, OOD Circuit Breaker, Constitutional Debate Loop |

---

## ⚖️ License

Documentation and source code are distributed under the MIT / Apache 2.0 licenses (see `LICENSE-MIT` and `LICENSE-APACHE` files).

---

*Black Swan © 2026. Technical preprint. Does not contain calls to action.*