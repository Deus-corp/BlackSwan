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
from typing import Any

logger = logging.getLogger(__name__)


class Proposal:
    """
    A trade proposal that needs approval from multiple swarm nodes.

    Attributes:
        proposer_node_id (str): The ID of the node that initiated the proposal.
        action (str): The proposed action (e.g., 'buy', 'sell').
        amount (float): The amount associated with the action.
        symbol (str): The asset symbol (e.g., 'BTC', 'ETH').
        signatures (dict[str, str]): A dictionary mapping node IDs to their cryptographic signatures for this proposal.
    """

    def __init__(self, proposer_node_id: str, action: str, amount: float, symbol: str) -> None:
        """
        Initialises a new Proposal.

        Args:
            proposer_node_id: The ID of the node initiating the proposal.
            action: The specific action proposed (e.g., 'buy', 'sell').
            amount: The quantity or value involved in the proposal.
            symbol: The asset symbol relevant to the proposal.
        """
        self.proposer_node_id: str = proposer_node_id
        self.action: str = action
        self.amount: float = amount
        self.symbol: str = symbol
        self.signatures: dict[str, str] = {}

    def sign(self, node_id: str, signature: str) -> None:
        """
        Adds a node's cryptographic signature to the proposal.

        Args:
            node_id: The ID of the node providing the signature.
            signature: The cryptographic signature from the node.
        """
        self.signatures[node_id] = signature

    def is_approved(self, quorum: int = 3) -> bool:
        """
        Checks if enough signatures have been collected to approve the proposal.

        Args:
            quorum: The minimum number of signatures required for approval. Defaults to 3.

        Returns:
            True if the number of collected signatures meets or exceeds the quorum, False otherwise.
        """
        return len(self.signatures) >= quorum

    def to_message(self) -> dict[str, Any]:
        """
        Serialises the proposal into a dictionary suitable for gossip transmission or storage.

        Returns:
            A dictionary representation of the proposal, including signatures.
        """
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

    Attributes:
        node_id (str): The ID of the node this manager is associated with.
    """

    def __init__(self, node_id: str) -> None:
        """
        Initialises the ConsensusManager for a specific node.

        Args:
            node_id: The ID of the current node.
        """
        self.node_id: str = node_id
        logger.info(f"ConsensusManager initialised (stub) for node {node_id}")

    def create_proposal(self, action: str, amount: float, symbol: str) -> Proposal:
        """
        Creates a new trade proposal initiated by this node.

        Args:
            action: The proposed action (e.g., 'buy', 'sell').
            amount: The amount involved in the proposal.
            symbol: The asset symbol.

        Returns:
            The newly created Proposal object.
        """
        return Proposal(self.node_id, action, amount, symbol)

    def process_signature(self, proposal: Proposal, node_id: str, signature: str) -> bool:
        """
        Processes an incoming signature for a given proposal.
        Adds the signature and then checks if the proposal is approved.

        Args:
            proposal: The proposal object to which the signature belongs.
            node_id: The ID of the node that provided the signature.
            signature: The cryptographic signature string.

        Returns:
            True if the proposal is approved after adding this signature, False otherwise.
        """
        proposal.sign(node_id, signature)
        return proposal.is_approved()