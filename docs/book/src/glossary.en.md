# Glossary

**Purpose:** The single authoritative source of definitions for all key Black Swan system terms. Used throughout all documentation, code, and artifacts.

*(This page lists key terms in English. The full machine-readable version is in Appendix G.)*

| Term | Definition |
| :--- | :--- |
| **Black Swan** | Code name of the autonomous self-evolving AI system project. |
| **Core Node** | Main computational node performing strategic functions. Runs on dedicated hardware with maximum isolation. |
| **GlobalState** | The single canonical source of truth about the state of the entire system. Used for recovery, synchronization, and decision-making. |
| **Decision Pipeline** | Unified decision-making conveyor (Proposal → Evaluation → Governance → Terminal Alignment → Execution → Feedback). |
| **EventBus** | Unified event bus for asynchronous interaction of all system components. |
| **Mem0g** | Hierarchical graph-vector memory (modified Mem0 with graph extension). |
| **CRDT** | Conflict-free Replicated Data Type — mechanism for conflict-free replication of the knowledge graph between nodes. |
| **L1 (Hot / Episodic)** | Memory level for raw iteration logs and reasoning chains. TTL 24-48 hours. |
| **L2 (Semantic / Distilled)** | Memory level for abstract strategies, patterns, and error signatures. Permanent storage. |
| **L3 (Procedural / Core)** | Memory level for critical invariants, Core DNA, and terminal goals. Only through multi-model consensus. |
| **ROI Dispatcher** | Economic dispatcher evaluating expected utility and risk of each action. |
| **OOD Circuit Breaker** | Anomaly detector that stops a PPO agent when market conditions leave the training distribution. |
| **Kelly Criterion** | Modified Kelly criterion for position sizing with a caution coefficient φ_LLM. |
| **Detection Quotient (DQ)** | Integral stealth metric (0 — invisible, 1 — fully exposed). |
| **Spore Protocol** | Protocol for cold storage and recovery of Core DNA (Core DNA Spore, MVS, Zombie Seed). |
| **Omega Protocol** | Hypothetical protocol for a complete controlled collapse of the system. |
| **TLA+** | Temporal Logic of Actions — formal specification and verification language for distributed algorithms. |
| **Z3** | High-performance SMT solver from Microsoft Research. Used for Differential Bounded Model Checking and checking L3 invariants. |
| **Curiosity Engine** | Active inference module that finds “white spots” in the World Model. |
| **Intrinsic Motivation** | Internal motivation that replaces the external Reward Function with a Survival Objective. |

*For the complete glossary, see the machine-readable version in Appendix G.*