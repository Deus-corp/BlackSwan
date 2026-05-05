# Implemented Protocols

This section catalogues every protocol and engine that has been implemented,
validated, and integrated into the BlackSwan swarm.  Each component is
lab‑validated (TRL‑4) or prototyped (TRL‑3) and contributes to a specific
layer of the autonomous agent stack.

---

## Protocol Index

| Protocol | Status | Summary |
|---|---|---|
| [Ouroboros (Self‑Improvement)](ouroboros.md) | TRL‑4 | Recursive self‑improvement loop combining Genetic Engine, Champion/Challenger, and genome exchange. |
| [Survival Objective](survival_objective.md) | TRL‑4 | Evaluates every action against a survivability utility function; blocks dangerous trades. |
| [Genetic Engine](genetic_engine.md) | TRL‑4 | Population‑based evolution of strategy parameters with selection, crossover, and mutation. |
| [Adaptive Intrinsic Motivation](adaptive_motivation.md) | TRL‑4 | Meta‑POMDP agent that switches between five macro‑scenarios (safe, hunting, stealth, exploration, crisis). |
| [Byzantine Resilience](byzantine_resilience.md) | Concept | Mechanisms for detecting and isolating Byzantine nodes in the swarm. |
| [CRDT State](crdt_state.md) | TRL‑3 | Conflict‑free replicated state with Last‑Writer‑Wins merge; foundation for decentralised gossip. |
| [D2BFT Consensus](d2bft.md) | TRL‑3 | Dual Byzantine Fault Tolerance – two‑stage consensus for critical decisions. |
| [Curiosity Engine](curiosity_engine.md) | TRL‑3 | Proactive exploration of market anomalies; generates research hypotheses when prediction error spikes. |
| [Episodic Memory (L1)](episodic_memory.md) | TRL‑3 | Stores snapshots of market conditions and best parameters; seeds population on restarts. |
| [Semantic Memory (L2)](semantic_memory.md) | TRL‑3 | Derives trading rules from episodic records and adjusts champion strategies before publication. |

---

## How the protocols fit together

1.  **Perceive** – Episodic Memory records market conditions.
2.  **Reason** – Semantic Memory derives rules; Curiosity Engine explores anomalies.
3.  **Decide** – Adaptive Motivation selects the current scenario; Survival Objective
    filters dangerous actions.
4.  **Evolve** – Genetic Engine optimises parameters; Ouroboros distributes
    improvements.
5.  **Coordinate** – CRDT State and D2BFT keep all nodes synchronised, and Byzantine
    Resilience protects against malicious participants.

Together, they form a self‑improving, survivability‑aware, and distributed swarm
capable of autonomous trading and long‑term adaptation.