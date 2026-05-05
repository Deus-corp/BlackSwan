# Swarm & Distribution

The Swarm & Distribution domain defines **how BlackSwan nodes discover each
other, share state, and coordinate actions** in a fully decentralised, P2P
network.  It replaces centralised servers with signed gossip, CRDT
replication, and Byzantine‑fault‑tolerant consensus.

---

## Key Documents

| Document | Focus |
|---|---|
| [Overview](README.en.md) | Introduction to swarm topology and communication. |
| [CRDT, Gossip & D2BFT](crdt_gossip_and_d2bft.en.md) | Conflict‑free replicated state, epidemic gossip, and two‑stage consensus. |
| [Swarm Topology](swarm_topology.en.md) | Node roles (Core, Regional Aggregator, Edge) and connectivity graph. |
| [Reputation & Coordination](reputation_and_coordination.en.md) | Reputation scoring for nodes, champion election, and collaborative decision‑making. |

---

## Communication Stack
```text
┌──────────────────────────┐
│ Application (strategies) │
├──────────────────────────┤
│ Consensus (D2BFT)        │ ← critical decisions require quorum
├──────────────────────────┤
│ State (CRDT)             │ ← conflict‑free replicated memory
├──────────────────────────┤
│ Transport (Gossip)       │ ← signed messages, replay protection
├──────────────────────────┤
│ Network (libp2p / TCP)   │ ← peer discovery, encryption
└──────────────────────────┘
```

This domain is the nervous system of the swarm — without it, nodes are
isolated agents; with it, they become a single, self‑healing organism.