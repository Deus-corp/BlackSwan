# CRDT State

**Status:** Prototype (TRL-3)

Conflict‑free Replicated Data Types (CRDTs) enable the swarm to share state
without a central coordinator. The current implementation uses a
Last‑Writer‑Wins (LWW) register for each key.

### Implementation
- `src/core/crdt_state.py` – LWW‑Register CRDT.
- Merge operation: when two nodes exchange state, the entry with the higher
  timestamp wins.

### Future work
- Gossip‑based synchronisation (periodic exchange with random peers).
- Integration into the Docker swarm, replacing Redis for state sync.