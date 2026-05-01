# Swarm Topology

**Purpose:** Describe the hierarchical architecture of the distributed swarm, the formal task scheduling model, the principles of species‑specific node specialization (Species‑Aware Topology), and the network topology taking into account security, performance, and stealth requirements. This module is the foundation for node coordination and state synchronization in a distributed environment.

---

## 1. Hierarchical topology

The swarm is organized into a three‑level hierarchy that optimizes the balance between computational power, latency, and cost. The fourth level — bio‑nodes (humans) — is integrated through the `Meat Interface`.

| Level | Hardware | Model used | Main functions |
| :--- | :--- | :--- | :--- |
| **Core Node** | 1× RTX PRO 6000 + 1–2× RTX 5090 Ti | DeepSeek‑V4 (Architectus / Sentinella masks) | Strategic decisions, Ouroboros cycle, BFT consensus, full validation |
| **Regional Aggregator** | VPS with GPU (A10 / RTX 4090) | DeepSeek‑V4 (Vagrant or Arbtiragius mask) | Log aggregation, local L1→L2 distillation, coordination of a group of Edge Nodes |
| **Edge Node** | Rented GPU (≥24 GB VRAM) | DeepSeek‑V4 (Vagrant mask, 20% experts) | Routine task execution, validation, code evolution |
| **Bio‑Node** | Human performer | — (interaction via interface) | Physical tasks: procurement, logistics, installation, KYC |

---

## 2. Formal scheduling model

### 2.1. Node Capability Matrix

Each node publishes its capabilities to `GlobalState.infrastructure_state` as a structured matrix. This allows the scheduler (`SwarmScheduler`) to precisely match task requirements with node capabilities.

**Example for an Edge Node:**
```json
{
  "node_id": "edge_12",
  "capabilities": {
    "compute": {
      "gpu_models": ["RTX 5090 Ti"],
      "vram_total_mb": 34816,
      "vram_available_mb": 30000,
      "supported_backends": ["cuda", "vulkan"]
    },
    "memory": {
      "ram_total_mb": 131072,
      "ram_available_mb": 100000
    },
    "storage": {
      "available_mb": 500000,
      "iops": 50000
    },
    "network": {
      "bandwidth_mbps": 1000,
      "latency_ms": 20,
      "nat_type": "full_cone"
    },
    "trust": {
      "tee_enabled": false,
      "reputation_score": 0.92
    }
  },
  "roles": ["code_generation", "shadow_testing"],
  "status": "online",
  "last_heartbeat": "2026-04-20T12:00:00Z"
}
```

### 2.2. Scheduler Policy

SwarmScheduler selects a node based on multi‑criteria optimization. Criteria and their weights are set in the scheduler policy and can be adapted by Meta‑Decision‑Pipeline.

Criterion	Weight	Description
Capability Match	mandatory	The node must meet the minimum task requirements (GPU, VRAM, TEE, Fast Path).
Latency	0.30	Minimizing RTT to the node.
Cost	0.30	Minimizing costs (GPU rental, electricity).
Reputation	0.20	Preference for nodes with high reliability and correctness.
Load	0.20	Load balancing (avoiding overloaded nodes).
Node selection pseudocode:

```python
def select_node(task: TaskSpec, available_nodes: List[Node]) -> Node:
    candidates = [n for n in available_nodes if matches_capabilities(n, task.required_capabilities)]
    scores = []
    for node in candidates:
        latency_score = 1.0 / (1.0 + node.latency_ms / 10.0)
        cost_score = 1.0 / (1.0 + node.cost_per_hour)
        rep_score = node.reputation_score
        load_score = 1.0 - node.current_load
        score = 0.3*latency_score + 0.3*cost_score + 0.2*rep_score + 0.2*load_score
        scores.append(score)
    return candidates[np.argmax(scores)]
```

### 2.3. Fast‑Path Routing

For tasks with high_frequency (PPO trading, MEV) or real_time (responses to security threats) priority, the scheduler uses Fast‑Path routing. Only nodes with fast_path_supported: true in their NodeCapabilityMatrix are selected. For such tasks, a hard latency budget is applied (default 50 ms) with post‑audit. Details are in Reputation_and_Coordination.md.

## 3. Species‑Aware Topology (Species‑specific node specialization)

The swarm is not homogeneous. Each node receives a species role, which is reflected in the topology, task scheduling, and hardware requirements. With the transition to DeepSeek‑V4, all species use a single base model but activate different subsets of experts, which determines VRAM and computational power requirements.

### 3.1. Species‑to‑hardware requirements matrix

Species	Activated experts	VRAM (estimate)	Recommended hardware
Arbtiragius	30%	~120 GB	1× RTX 5090 Ti (32 GB) + CPU offload
Sentinella	40%	~160 GB	2× RTX 5090 Ti or 1× RTX PRO 6000
Architectus	60%	~240 GB	2× RTX PRO 6000 or 4× RTX 5090 Ti
Vagrant	20%	~80 GB	1× RTX 4090 / rental
3.2. Dynamic activation of expert masks
A node of a particular species is launched with the --expert-mask and --expert-percent parameters passed to vLLM. This allows:
Saving VRAM: unused experts are not loaded.
Accelerating inference: fewer experts → fewer computations.
Strengthening isolation: Sentinella physically cannot activate experts optimized for risky trading.
In critical situations, a node can temporarily activate additional experts via meta_proposal and the Decision Pipeline.

### 3.3. Species‑specific quorums

Since all species use the same base model, trust between them is higher. However, critical decisions still require a quorum of different species. The votes of two Arbtiragius nodes count as one vote for that species. Changing the expert mask requires a BFT quorum.

### 3.4. Synchronization of expert masks via CRDT

The expert masks of species are stored in GlobalState.infrastructure_state and synchronized via CRDT. This guarantees that all swarm nodes have an up‑to‑date view of each other's specialization.

## 4. Integration with other modules

Module	Connection
Reputation_and_Coordination.md	Reputation and scheduler use the node capability model from this module.
CRDT_Gossip_and_D2BFT.md	Topology defines which nodes participate in BFT and gossip.
Isolation_and_Sandbox.md	Sandbox isolation profiles depend on the node species.
Meat_Interface_Tasking.md	Bio‑nodes are registered in the topology as bio‑node.
Global_State_and_Decision_Pipeline.md	infrastructure_state stores topology and expert masks.
Memory_Hierarchy_Mem0g.md	The CRDT knowledge graph is distributed according to the topology.