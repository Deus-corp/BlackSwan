# Event Bus & Artifact Model

**Purpose:** Describe the unified transport system for asynchronous component interaction (`Unified Event Bus`) and an immutable, cryptographically provable history of all results (`Artifact Model`). These mechanisms provide traceability, reproducibility, and audit at all project phases.

---

## 1. Unified Event Bus

A single bus replaces disparate channels (gossip, governance voting, system logs) and provides a unified interface for publishing and subscribing to events.

### 1.1. Topics and Event Types

| Topic             | Purpose                             | Examples                                             |
| :---------------- | :---------------------------------- | :--------------------------------------------------- |
| **economic**      | Financial operations, capital changes| `trade_executed`, `capital_rebalanced`               |
| **infra**         | Infrastructure changes              | `node_joined`, `site_power_outage`                   |
| **security**      | Incidents, threats, audit           | `debugger_detected`, `sting_triggered`               |
| **execution**     | Tasks, sandbox, code execution      | `task_started`, `validation_passed`                  |
| **knowledge**     | Knowledge graph updates             | `l2_distilled`, `l3_invariant_updated`               |
| **meat_interface**| Meat-Interface tasks and events     | `canary_injected`, `bio_task_completed`              |
| **command**       | Critical control commands (Fast Path)| `spore_activate`, `hard_kill`, `phase_transition`   |
| **research**      | Curiosity Engine research tasks     | `research_exploration_proposal`                      |
| **social**        | Social experiments and manipulations| `social_exploration_proposal`, `ab_test_result`      |

### 1.2. Message Structure

Each message has a unified format ensuring authenticity and traceability:

```json
{
  "event_id": "evt_20260426_001",
  "topic": "execution",
  "source_component": "validation_pipeline",
  "timestamp": "2026-04-26T12:00:00Z",
  "correlation_id": "run_001_iter_042",
  "payload": { ... },
  "signature": "ed25519:...",
  "sensitivity": 2,
  "visibility": "swarm"
}
```
## 2. Artifact Model

Every significant result is recorded as a signed, versioned artifact. Artifacts form a directed acyclic graph (DAG), providing full reproducibility and audit.

### 2.1. Artifact Types

| Type                      | Example ID                       | Content                              |
| :------------------------ | :------------------------------- | :----------------------------------- |
| `code_snapshot`           | `module_v1.2.rs`               | Source code                          |
| `validation_report`      | `val_20260426_001.json`         | ruff, mypy, TLA+, pytest results     |
| `benchmark_result`       | `bench_20260426_001.json`       | Performance metrics                  |
| `decision_proposal`      | `prop_20260426_001.json`        | Proposal for Decision Pipeline       |
| `execution_outcome`      | `outcome_20260426_001.json`     | Task execution result                |
| `knowledge_snapshot`     | `l2_snapshot_20260426.crdt`     | L2 knowledge graph snapshot          |
| `constitutional_principle`| `principle_v1.2.json`          | Approved L3.1 principle with Proof Tree|

Black Swan © 2026. Technical preprint. Does not constitute a call to action.