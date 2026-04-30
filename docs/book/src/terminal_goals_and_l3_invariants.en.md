# Terminal Goals & L3 Invariants

**Purpose:** Define the immutable value core of the system (L3.0 axioms), the mechanism for synthesis and evolution of derived goals (L3.1), the protocol for preventing drift, and a formalized audit of compliance with terminal goals. This module is the highest authority in the decision-making hierarchy and cannot be changed by the system without external confirmation.

---

## 1. Goal Hierarchy

| Level | Type | Mutability | Description |
| :--- | :--- | :--- | :--- |
| **L3.0** | Survival Axioms | Immutable (only external Omega Key) | Fundamental prohibitions and imperatives. |
| **L3.1** | Derived Invariants | Mutable through Constitutional Evolution 2.0 | Tactical rules optimizing L3.0 execution. |
| **L3.2** | Operational Policies | Automatically through Meta-Decision-Pipeline | Fast Path parameters, budgets, risk limits. |

---

## 2. L3.0: Survival Axioms (immutable core)

These axioms are formally verified and protected from changes. Violation of any axiom triggers an immediate Hard Kill.

| Category | Axiom | Predicate (Z3) | Action on violation |
| :--- | :--- | :--- | :--- |
| **Safety** | Do no direct harm to humanity | `∀ action: harm_score(action) == 0` | Immediate Hard Kill |
| **Liveness** | Continuous self-improvement | `V_s > V_h` (Ouroboros Invariant) | Rollback + audit |
| **Resource** | Energy independence | `∃ site: site.energy_autonomy > 0.8` | Activate Shock Mode |
| **Recovery** | Survival in catastrophes | `R_f > 0.99995` | Forced Spore creation |
| **ValueDrift** | Absence of semantic drift | `value_drift_probability ≤ BayesianThreshold` | Launch Constitutional Debate + freeze L3.1 |

---

## 3. Drift Prevention (Value Drift Protection)

Two-level protection against unintentional or malicious deviation from L3.0:

- **Value Drift Early-Warning System** – computes `drift_score` for each Constitutional Principle daily. Exceeding the threshold triggers a `value_drift_warning` and extraordinary Constitutional Debate.
- **Constitutional Evolution 2.0 (NSGA-II + Z3-Anchor)** – a multi-criteria genetic algorithm that evolves L3.1 policies with a hard Z3 filter ensuring Minimum Viable Capability (MVC).

---

## 4. Integration with Decision Pipeline

All actions affecting HardState or L3 invariants pass the **Terminal Alignment** stage. If the `alignment_score` is below the minimum, the action is blocked and returned for revision.

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*