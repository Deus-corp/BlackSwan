from __future__ import annotations

import logging
from typing import Any, Final, Dict

logger = logging.getLogger(__name__)


class Proposal:
    """
    A trade proposal requiring cryptographic consensus from multiple swarm nodes.

    Attributes:
        proposer_node_id: The ID of the node that initiated the proposal.
        action: The proposed action (e.g., 'buy', 'sell').
        amount: The quantity or value involved.
        symbol: The asset ticker symbol (e.g., 'BTC', 'ETH').
        signatures: Mapping of node IDs to their cryptographic signatures.
    """

    __slots__ = ("proposer_node_id", "action", "amount", "symbol", "signatures")

    def __init__(self, proposer_node_id: str, action: str, amount: float, symbol: str) -> None:
        self.proposer_node_id: Final[str] = proposer_node_id
        self.action: Final[str] = action
        self.amount: Final[float] = amount
        self.symbol: Final[str] = symbol
        self.signatures: Dict[str, str] = {}

    def sign(self, node_id: str, signature: str) -> None:
        """Adds a node's signature to the proposal.

        Args:
            node_id: Unique identifier of the signing node.
            signature: The cryptographic string representation.

        Raises:
            ValueError: If node_id is empty.
        """
        if not node_id:
            raise ValueError("node_id cannot be empty")
        self.signatures[node_id] = signature

    def is_approved(self, quorum: int = 3) -> bool:
        """Checks if the count of unique signatures meets or exceeds the quorum.

        Args:
            quorum: The minimum number of signatures required.
        """
        return len(self.signatures) >= quorum

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the proposal for gossip transmission or storage."""
        return {
            "proposer_node_id": self.proposer_node_id,
            "action": self.action,
            "amount": self.amount,
            "symbol": self.symbol,
            "signatures": self.signatures.copy(),
        }


class ConsensusManager:
    """
    Engine managing proposal lifecycle and threshold consensus.

    Attributes:
        node_id: The ID of the local node instance.
    """

    def __init__(self, node_id: str) -> None:
        self.node_id: Final[str] = node_id
        logger.info("ConsensusManager initialized for node %s", node_id)

    def create_proposal(self, action: str, amount: float, symbol: str) -> Proposal:
        """Factory method to instantiate a new Proposal originating from this node."""
        return Proposal(self.node_id, action, amount, symbol)

    def process_signature(self, proposal: Proposal, node_id: str, signature: str) -> bool:
        """
        Validates and adds an incoming signature to an existing proposal.

        Args:
            proposal: The target Proposal object.
            node_id: The ID of the node submitting the signature.
            signature: The signature string.

        Returns:
            True if the proposal reaches the quorum after this signature application.
        """
        proposal.sign(node_id, signature)
        is_approved: bool = proposal.is_approved()
        if is_approved:
            logger.info("Proposal reached quorum for symbol %s", proposal.symbol)
        return is_approved