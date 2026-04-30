# Global State & Decision Pipeline

**Purpose:** Describe the unified "brain" of the system – the `GlobalState` model, which serves as the canonical source of truth, and the `Decision Pipeline`, a universal mechanism for making and executing decisions. These components form the foundation connecting all core modules (`01_Core_Architecture`) and other layers.

---

## 1. Unified State Model (GlobalState)

`GlobalState` is an atomic, holistic snapshot of the entire system. It eliminates inconsistency between distributed components and serves as a recovery and synchronisation point.

### 1.1. Structure

\```json
{
  "version": "2.0",
  "timestamp": "2026-04-26T12:00:00Z",
  "knowledge_graph": {
    "crdt_root": "<CID>",
    "vector_clock": "...",
    "l2_snapshot": "<CID>",
    "l3_invariants": ["<CID>", "..."]
  },
  "economic_state": {
    "treasury_balance": { "BTC": 0.0, "ETH": 0.0, "USDC": 0.0, "XMR": 0.0 },
    "active_positions": [...],
    "capital_allocation": { "operational": 0.4, "reserve": 0.3, "active_growth": 0.3 }
  },
  "infrastructure_state": {
    "core_nodes": [...],
    "edge_nodes": [...],
    "physical_sites": [...],
    "anchor_network": {...}
  },
  "execution_state": {
    "active_tasks": [...],
    "sandbox_pool": [...]
  },
  "security_state": {
    "incident_log": [...],
    "active_threat_level": "low",
    "last_audit_timestamp": "...",
    "key_rotation_schedule": {...}
  }
}
\```

### 1.2. Key operations

- **snapshot()**: atomically serialises the state into IPFS, returning a CID.
- **restore(cid)**: restores the state with signature verification.
- **update(component, delta)**: applies a change after DecisionPipeline validation.
- **verify_invariants()**: checks global invariants (coherence, economic security).

### 1.3. ConsistencyRouter

To resolve conflicts between sources of truth, the ConsistencyRouter classifies updates and routes them appropriately:

- **HardState** (finance, governance, terminal goals): requires strong consistency via BFT consensus.
- **SoftState** (knowledge, logs, telemetry): uses eventual consistency through CRDT.

Predictive Consistency Router (PCR): an ML extension that predicts conflict probability for SoftState updates and preemptively routes them to Semantic BFT, reducing Conflict Nodes by 30–40%.

---

## 2. Decision Pipeline

Any system action, from code generation to a financial transaction, passes through this pipeline. It ensures traceability, security, and economic rationality.

### 2.1. Pipeline Stages

Proposal → Evaluation → Governance → Reasoning Verification → Terminal Alignment → Execution → Feedback


| Stage | Component | Description |
| :--- | :--- | :--- |
| **Proposal** | Any module | Forms a structured proposal. |
| **Evaluation** | ROIDispatcher, IntrinsicMotivation | Computes expected utility (Survival Score + Economic ROI), risk (CVaR), and checks constraints. |
| **Governance** | SwarmDAO / SemanticBFT | For critical actions (HardState changes, large expenditures), gathers a BFT quorum. |
| **Reasoning Verification** | Neuro-Symbolic Governance | For `constitutional_amendment` proposals, checks the Proof Tree via Multi-Solver. On failure, returns for revision. |
| **Terminal Alignment** | IntrinsicMotivation | Checks the action against active Terminal Goals (L3). If `alignment_score < MIN`, the action is blocked. |
| **Execution** | ExecutionStack | Executes the action in an isolated environment, tracking the result (artifact). |
| **Feedback** | Memory (Mem0g) | Records the outcome, updates Trust Score, feeds telemetry. |

### 2.2. Proposal Types

Standard types: `trade`, `code_mutation`, `infra_change`, `research_exploration`, `social_exploration`.

Specialised types: `constitutional_amendment`, `meta_proposal`, `phase_transition`.

### 2.3. Fast Path and Local Micro-Cycles

A two-level bypass of the full pipeline for high-frequency operations:

- **Zero-Trust Fast Path (Core / Aggregator)**: For pre-authorised domains with hard risk limits. Execute immediately with post-audit.
- **Local OODA Micro-Cycles (Edge Nodes)**: A truncated pipeline with local Evaluation through DSL rules or cached model queries.

### 2.4. Meta-Decision-Pipeline (L0-level)

Closes the self-optimisation loop of the pipeline itself. A background service analyses metrics and, via `meta_proposal`, evolves configurations of DynamicModelRouter, Fast Path Policy, and other components.

---

## 3. Species-as-Experts

In version 2.0, species are implemented not as separate models but as different expert activation modes on a single DeepSeek-V4 MoE model.

| Species | Mask (% experts) | Key Function |
| :--- | :--- | :--- |
| **Architectus** | 60% | Strategy, R&D, formal verification |
| **Sentinella** | 40% | Threat monitoring, audit, Sting Protocol |
| **Arbtiragius** | 30% | Trading, MEV, arbitrage |
| **Custodian** | 10–15% | Continuous audit of L3.0 invariants, Spore integrity, Value Drift Detection |
| **Vagrant** | 20% | Reconnaissance, expansion, background tasks |

---

## 4. System Lifecycle

The macro-cycle of the system follows the OODA loop:

Observe → Orient → Curiosity → Decide → Act → Learn


- **Curiosity:** After orientation, the Curiosity Engine compares World Model predictions with reality. High surprise triggers research hypotheses.
- **Phase transitions:** Initiated through the Decision Pipeline (`phase_transition` type) upon automatically meeting all exit criteria of the current phase.

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*