# D2BFT Consensus

**Status:** Prototype (TRL-3)

D2BFT (Dual Byzantine Fault Tolerance) is the consensus protocol designed
for the BlackSwan swarm. The current prototype implements simple majority
voting among 3+ nodes.

### Implementation
- `src/core/d2bft.py` – D2BFTNode class.
- Nodes propose a value and exchange votes; consensus is reached when a
  value receives a majority of votes.

### Formal model
`formal/tla/D2BFT.tla` describes the full two‑stage protocol.
The Python prototype will be extended to match the TLA+ specification.

### Next steps
- Integrate with CRDT state for automatic synchronisation of critical decisions.
- Replace Redis pub/sub for consensus messages.