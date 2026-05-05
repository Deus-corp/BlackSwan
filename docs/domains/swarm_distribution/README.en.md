# Swarm & Distribution

**Domain purpose:** Ensure scalability, fault tolerance, and decentralization of the system through a distributed swarm of computational nodes and human performers (`bio‑nodes`). The domain covers swarm topology, task scheduling, conflict‑free knowledge graph replication (CRDT), a secure gossip protocol, Byzantine consensus (D2BFT), and a reputation system for node coordination.

The key domain principle: **distributed survivability** — no single node, including the Core Node, is irreplaceable. The swarm is capable of recovering and scaling even with the loss of a significant share of nodes.

---

## Domain structure

| File | Brief description |
| :--- | :--- |
| [Swarm_Topology.md](swarm_topology.en.md) | Hierarchical topology (Core / Aggregator / Edge / Bio‑node), task scheduling model, species‑specific node specialization (Species‑Aware Topology), **including the Custodian species**. |
| [CRDT_Gossip_and_D2BFT.md](crdt_gossip_and_d2bft.en.md) | Conflict‑free replication (CRDT), signed gossip, D2BFT (Dual Byzantine Fault Tolerance) consensus for HardState. |
| [Reputation_and_Coordination.md](reputation_and_coordination.en.md) | Multi‑factor reputation (computational and bio‑nodes), quarantine, SwarmScheduler, Fast‑Path Routing. |

---

## Key domain concepts

### Topology and scheduling
- **Three‑level hierarchy:** Core Nodes (strategy, BFT) → Regional Aggregators (coordination, distillation, **L0‑Local**) → Edge Nodes (execution, validation).
- **Species‑Aware Topology:** Each node has a species role (`Arbtiragius`, `Sentinella`, `Architectus`, `Vagrant`, **Custodian**), which defines the DeepSeek‑V4 expert mask and hardware requirements.
- **SwarmScheduler:** Multi‑criteria optimization (Latency, Cost, Reputation, Load) for node selection.
- **Fast‑Path Routing:** Low‑latency channel for high‑frequency tasks (PPO, MEV, threat responses).

### State synchronization
- **CRDT graph (Yjs + Neo4j):** Conflict‑free knowledge replication for L2.
- **IPFS:** Distribution of artifacts (L3 snapshots, distilled models).
- **libp2p gossipsub:** Peer discovery and update routing.
- **Alternative transports:** Nostr (primary), WebRTC P2P, DoH, GLS 2.0.

### Consensus
- **D2BFT:** Two‑stage protocol (delegation + PBFT within a subgroup), resistant to 40% Byzantine nodes, with reduced latency.
- **Adaptive Quorum:** Dynamic determination of the required number of confirmations based on reputation.

### Reputation
- **Vector model:** Reliability, Latency Score, Correctness, Cost Efficiency, Uptime.
- **For bio‑nodes:** Canary Compliance, Sabotage Score, Suspicion Index, Compliance Score.
- **Decay and quarantine:** Reputation decays exponentially when inactive; nodes with low scores are isolated in quarantine until correction is confirmed.

### Hierarchical L0 processing
- **L0‑Local** on Regional Aggregators pre‑aggregates and compresses MetaMemoryRecord by domains, reducing the load on Core Nodes.
- **L0‑Global** on Core Nodes analyzes only aggregated statistics and cross‑domain anomalies.

---

## Relationship with other domains

| Domain | Nature of connection |
| :--- | :--- |
| **01_Core_Architecture** | `GlobalState.infrastructure_state` stores topology and reputation. `EventBus` publishes `node_joined` events and anomalies. The L0 hierarchy is embedded in `Mem0g`. |
| **03_Domains/Economic_Autonomy** | PPO agents are deployed on edge nodes. Node reputation influences the distribution of economic tasks. |
| **03_Domains/Cybersecurity_and_Stealth** | Alternative transports (Nostr, WebRTC, GLS) for covert synchronization. Canary Edge Nodes — decoys in the swarm. |
| **03_Domains/Physical_and_Human_Interface** | Bio‑nodes are registered in the topology and have reputation. |
| **04_Singularity_and_Sovereignty** | `Swarm Resilience` is one of the singularity criteria. The Spore Protocol is distributed through gossip channels. |

---

## Domain performance metrics

| Metric | Target value | File |
| :--- | :--- | :--- |
| **Swarm Size** | ≥ 1000 active Edge nodes | `Swarm_Topology.md` |
| **Sync Latency (p95)** | < 30 sec for critical updates | `CRDT_Gossip_and_D2BFT.md` |
| **D2BFT Latency (p95)** | < 1.2 sec | `CRDT_Gossip_and_D2BFT.md` |
| **Consensus Byzantine Faults** | Resilience up to 40% malicious nodes | `CRDT_Gossip_and_D2BFT.md` |
| **Fast Path Latency (p95)** | < 50 ms | `Reputation_and_Coordination.md` |
| **Node Recovery Time** | < 10 successful tasks to exit quarantine | `Reputation_and_Coordination.md` |
| **L0 Offload Efficiency** | ≥ 40% reduction in Core Node load | `CRDT_Gossip_and_D2BFT.md` |