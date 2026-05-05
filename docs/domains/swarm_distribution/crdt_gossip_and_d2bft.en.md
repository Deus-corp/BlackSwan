# CRDT, Gossip & D2BFT (Distributed Consensus and Synchronization)

**Purpose:** Ensure the integrity and synchronization of the distributed knowledge graph and swarm state under unreliable network conditions and active countermeasures. This module describes conflict‑free replication mechanisms (CRDT), a secure gossip protocol, and the `D2BFT` (Dual Byzantine Fault Tolerance) Byzantine consensus for critical decisions affecting HardState.

---

## 1. CRDT / IPFS / libp2p Fabric

### 1.1. Conflict‑free knowledge graph replication

The swarm uses a combination of technologies for state synchronization:

- **Yjs + CRDT** — collaborative editing of the knowledge graph and metadata.
- **IPFS** — distribution of artifacts (L3 snapshots, distilled models).
- **libp2p gossipsub** — peer discovery and update routing.
- **Vector clocks** — conflict resolution in Mem0g metadata.

### 1.2. Canonical CRDT object structure

```json
{
  "schema_version": "2.0",
  "object_id": "uuid-1234",
  "type": "KnowledgeNode",
  "content": {
    "statement": "Use async for I/O-bound operations",
    "embedding": [0.1, 0.2, ...]
  },
  "metadata": {
    "vector_clock": {"node_A": 5, "node_B": 3},
    "timestamp": "2026-04-20T12:00:00Z",
    "creator": "node_A",
    "signature": "ed25519:..."
  },
  "links": [
    {"target": "uuid-5678", "type": "derived_from"}
  ]
}
```

## 2. Signed Gossip and synchronization

### 2.1. Gossip message structure

```rust
struct GossipMessage {
    message_id: [u8; 32], // BLAKE3 content hash
    prev_message_id: Option<[u8; 32]>, // for causality
    topic: String,
    payload: Vec<u8>,
    timestamp: u64,
    ttl: u32,
    creator_id: String,
    signature: Vec<u8>, // Ed25519
}
```

### 2.2. Protection against forgery and spam

All gossip messages are signed with Ed25519 (or Dilithium5).
Rate limiting via token bucket (5 messages/sec per node).
Key rotation every 30 days. Old public keys are stored in GlobalState.security_state.

### 2.3. Hierarchical Gossip with Adaptive Quorum

Core Nodes exchange the full graph via BFT consensus.
Regional Aggregators receive updates from Core Nodes and relay them to edge nodes in their zone.
Edge Nodes participate only in local gossip with the aggregator.
Adaptive Quorum: For critical updates (HardState), the required number of confirmations is computed dynamically based on the current reputation of nodes:

```python
def adaptive_quorum(nodes: List[Node]) -> int:
    total_weight = sum(node.reputation_score for node in nodes)
    return max(3, int(0.67 * total_weight))
```

## 3. Swarm-BFT 2.0: Dual Byzantine Fault Tolerance (D2BFT)

### 3.1. Rationale for transition

Classic Swarm-BFT (PBFT) provides reliability up to 1/3 Byzantine nodes, but its performance (O(N²) messages) becomes a limiting factor when scaling. D2BFT demonstrates the ability to withstand up to 40% malicious nodes and reduces consensus latency by ~20% compared to PBFT.

### 3.2. D2BFT architecture

D2BFT is a two‑stage protocol:
DBFT phase (Delegation):
A subgroup of validators is selected from the Core node pool based on reputation and a stochastic algorithm.
The subgroup size is configurable (validator_count = 7).
PBFT phase (Consensus within the subgroup):
The selected validators run a lightweight PBFT‑like protocol to reach final agreement.
Communication complexity is reduced to O(m²), where m << n.

### 3.3. D2BFT core pseudocode

```rust
impl D2BFT {
    async fn run_round(&mut self, proposal: Proposal) -> Result<ConsensusResult, Error> {
        // 1. DBFT phase: Delegation
        let validator_set = self.select_validators(
            &self.core_nodes, self.config.validator_count, &self.reputation_scores
        ).await?;

        // 2. PBFT phase: Fast consensus within the selected group
        let leader = self.elect_leader(&validator_set);
        let pbft_result = self.run_pbft_round(leader, &validator_set, proposal).await?;

        // 3. Commit result and update reputation
        if pbft_result.is_committed() {
            self.commit(proposal).await?;
            Ok(ConsensusResult::Committed)
        } else {
            Err(ConsensusError::CommitFailed)
        }
    }
}
```

## 3.4. Performance metrics

Metric	Swarm-BFT (old)	D2BFT (new)	Target improvement
Max share of malicious nodes	33%	40%	+7%
Consensus latency (p95)	1.5 sec	~1.2 sec	-20%
Communication complexity	O(n²)	O(m²), m << n	Significant reduction

### 3.5. Configuration

```json
{
  "consensus": {
    "protocol": "d2bft",
    "validator_count": 7,
    "leader_rotation_interval": 60,
    "view_change_timeout_ms": 3000,
    "max_byzantine_faults": 0.40
  }
}
```

## 4. Integration with other modules

Module	Connection
Swarm_Topology.md	Topology defines which nodes participate in BFT and gossip.
Reputation_and_Coordination.md	Reputation is used for validator selection and Adaptive Quorum.
Memory_Hierarchy_Mem0g.md	CRDT graph is the implementation of distributed L2 memory.
Stealth_and_C2.md	Alternative transports (Nostr, WebRTC) for covert synchronization.
Global_State_and_Decision_Pipeline.md	HardState changes pass through D2BFT at the Governance stage.

