# Survival Objective

**Status:** TRL-4 (integrated into every swarm node)

The Survival Objective ensures that nodes prioritise long‑term existence
over short‑term profit. Every action is evaluated by the formula:

U = log(P(Liveness) / P(Detection)) + λ·log(Capital)


### Key features
- **Trade rejection** – trades that would raise the Detection Quotient (DQ)
  above a safe threshold are automatically blocked.
- **Hide/Expand** – nodes can sacrifice capital to reduce DQ or improve
  liveness (e.g., spawning a new node).
- **Formal model** – `SurvivalObjective.tla` proves that the system never
  violates critical DQ and capital bounds.

### Implementation
- `sim/survival_evaluator.py` – Python evaluator used by every node.
- Monitored via log messages: `trade rejected (survival risk)`, `hides`, `expands`.