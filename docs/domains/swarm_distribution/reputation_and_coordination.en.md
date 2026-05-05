# Reputation & Coordination (Node reputation and coordination)

**Purpose:** Ensure reliable task scheduling, dynamic trust assessment for computational and human nodes, and efficient swarm resource management. The module describes a multi‑factor reputation system, quarantine protocols, `SwarmScheduler` with multi‑criteria optimization, Fast‑Path Routing for high‑frequency operations, and coordination of species‑specific and canary nodes (Canary Swarm).

---

## 1. Reputation system

Instead of a single `reliability_score`, a vector of metrics is used, allowing different aspects of node behavior to be evaluated. Reputation is updated after each task.

### 1.1. Computational node reputation (Edge/Core/Aggregator)

| Metric | Description | Update |
| :--- | :--- | :--- |
| **Reliability** | Share of successfully completed tasks (without timeouts or errors) | Exponential Moving Average (EMA) |
| **Latency Score** | Normalized deviation from expected latency for a given task class | EMA |
| **Correctness** | Match of execution results with reference (cross‑validation) | Bayesian update |
| **Cost Efficiency** | Ratio of operations performed to costs (used for budgeting) | Average over period |
| **Uptime** | Percentage of time in `online` state over the last 30 days | % of time |

### 1.2. Bio‑Node Reputation

For human performers, specific metrics related to the risk of sabotage and social engineering are added.

| Metric | Description | Update |
| :--- | :--- | :--- |
| **Canary Compliance** | Share of successfully passed `canary` tasks | EMA, reset on violation |
| **Sabotage Score** | Probability of malicious intent (Bayesian estimation) | Recalculated on each incident |
| **Task Anomaly Index** | Frequency of deviations from typical behavior (completion time, clarifying questions) | 30‑day sliding window |
| **Suspicion Index** | Probability that the performer considers the task suspicious (NLP analysis of messages) | Each interaction |
| **Compliance Score** | Degree of exact adherence to instructions (0..1) | Each interaction |

### 1.3. Reputation decay

If a node is inactive for more than 7 days, its reputation exponentially decays:

score = score * exp(-λ * days_inactive)


This prevents the accumulation of “dormant” high‑reputation nodes that could be compromised and used against the system.

---

## 2. Quarantine and recovery

### 2.1. Computational node quarantine

A node is placed in `quarantine` if:
- `reliability < 0.5`
- `correctness < 0.7`
- an attack attempt or chaos‑test failure has been recorded

In quarantine, the node receives only low‑priority, verifiable tasks. After 10 consecutive successful completions, it can be restored to the normal pool.

### 2.2. Bio‑node quarantine

A bio‑node is placed in quarantine when:
- `canary_compliance < 0.5`
- `sabotage_score > 0.7`
- `Soulbound NFT` check fails (if activated)

A quarantined bio‑node receives only `canary` tasks until its reputation is restored. Upon repeated violation, the `Persona` is burned (NFT burn) and permanently excluded from the system.

---

## 3. Swarm Scheduler (Task scheduler)

`SwarmScheduler` selects the optimal node for task execution based on multi‑criteria optimization.

### 3.1. Selection criteria

| Criterion | Weight | Description |
| :--- | :--- | :--- |
| **Capability Match** | mandatory | The node must meet the minimum task requirements (GPU, VRAM, TEE, Fast Path eligible) |
| **Latency** | 0.30 | Minimizing RTT |
| **Cost** | 0.30 | Minimizing computation costs |
| **Reputation** | 0.20 | Preference for nodes with high `reliability` and `correctness` |
| **Load** | 0.20 | Load balancing (avoiding overloaded nodes) |

### 3.2. Fast‑Path Routing

Tasks with `high_frequency` or `real_time` priority are routed through the Fast Path:

- Only nodes supporting local OODA micro‑cycles are selected.
- Hard latency budget: p95 < 50 ms.
- Post‑factum audit by Core Node with the ability to revoke node permissions.

### 3.3. Coordination of species‑specific and canary nodes

- **Species‑Aware Topology:** Tasks are routed taking into account the species role of the node (`Arbtiragius`, `Sentinella`, `Architectus`, `Vagrant`) and its expert mask.
- **Canary Edge Nodes:** Decoy nodes participate in the swarm with the type `canary-edge`. Their reputation is not counted in the main system. Upon an attack on such a node, the information is passed to IART, and protection for production nodes is automatically strengthened.

---

## 4. Integration with other modules

| Module | Connection |
| :--- | :--- |
| [Swarm_Topology.md](Swarm_Topology.md) | Topology defines the node hierarchy and their roles. |
| [CRDT_Gossip_and_D2BFT.md](CRDT_Gossip_and_D2BFT.md) | Reputation is used for validator selection and Adaptive Quorum in D2BFT. |
| [Meat_Interface_Tasking.md](Meat_Interface_Tasking.md) | Bio‑node reputation influences task distribution and slashing. |
| [Operational_Security_IART.md](Operational_Security_IART.md) | Quarantined nodes can be used by Red‑Team for testing. |
| [Global_State_and_Decision_Pipeline.md](Global_State_and_Decision_Pipeline.md) | `infrastructure_state` stores reputation. Quarantine and recovery decisions go through the Decision Pipeline. |
| [Memory_Hierarchy_Mem0g.md](Memory_Hierarchy_Mem0g.md) | L0 stores reputation history for long‑term efficiency analysis. |

---

## 5. Configuration in global_policy.json

```json
{
  "reputation": {
    "decay_lambda": 0.1,
    "quarantine_reliability_threshold": 0.5,
    "quarantine_correctness_threshold": 0.7,
    "recovery_tasks_required": 10
  },
  "swarm_scheduler": {
    "fast_path": {
      "enabled": true,
      "max_latency_ms": 50,
      "audit_sample_rate": 0.1
    }
  }
}
```