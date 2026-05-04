# src/consensus/proposal.py
"""
Consensus proposal layer (stub).
In the future, this will manage:
- Creating and signing trade proposals.
- Broadcasting proposals via gossip.
- Collecting signatures from other nodes.
- Verifying that a quorum (e.g., 3/4) has been reached.
- Submitting the signed transaction to a Multi-Sig Safe (Gnosis Safe)
  or executing a threshold signature scheme.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Proposal:
    """
    A trade proposal that needs approval from multiple swarm nodes.
    Currently a stub that always returns "approved".
    """

    def __init__(self, proposer_node_id: str, action: str, amount: float, symbol: str):
        self.proposer_node_id = proposer_node_id
        self.action = action
        self.amount = amount
        self.symbol = symbol
        self.signatures: dict = {}

    def sign(self, node_id: str, signature: str) -> None:
        """Add a node's cryptographic signature to the proposal."""
        self.signatures[node_id] = signature

    def is_approved(self, quorum: int = 3) -> bool:
        """Check if enough signatures have been collected."""
        return len(self.signatures) >= quorum

    def to_message(self) -> dict:
        """Serialise the proposal for gossip transmission."""
        return {
            "proposer_node_id": self.proposer_node_id,
            "action": self.action,
            "amount": self.amount,
            "symbol": self.symbol,
            "signatures": self.signatures,
        }


class ConsensusManager:
    """
    Placeholder for the consensus engine.
    Will eventually handle proposal creation, signature collection,
    Multi-Sig Safe interaction, and final transaction submission.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        logger.info(f"ConsensusManager initialised (stub) for node {node_id}")

    def create_proposal(self, action: str, amount: float, symbol: str) -> Proposal:
        """Create a new proposal and return it."""
        return Proposal(self.node_id, action, amount, symbol)

    def process_signature(self, proposal: Proposal, node_id: str, signature: str) -> bool:
        """Process an incoming signature for a proposal."""
        proposal.sign(node_id, signature)
        return proposal.is_approved()