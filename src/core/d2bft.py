"""
Minimal implementation of a D2BFT (Delegated Byzantine Fault Tolerance) consensus node.

This module provides a mechanism for nodes to propose values and reach consensus
through a simple majority voting system.
"""
from typing import Any, Dict, Optional, Final
from collections import Counter

class D2BFTNode:
    """
    Represents a single node in a D2BFT consensus group.

    The node facilitates value proposal and vote collection. A consensus decision
    is reached when a value receives more than N/2 votes from the participating nodes.
    """

    __slots__ = ("node_id", "total_nodes", "current_view", "votes", "decision")

    def __init__(self, node_id: str, total_nodes: int = 3) -> None:
        """
        Initializes the node with a unique identifier and cluster size.

        Args:
            node_id: Unique identifier for the node.
            total_nodes: Total count of nodes in the consensus group.

        Raises:
            ValueError: If inputs are invalid.
        """
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be a non-empty string.")
        if not isinstance(total_nodes, int) or total_nodes < 1:
            raise ValueError("total_nodes must be a positive integer.")

        self.node_id: Final[str] = node_id.strip()
        self.total_nodes: Final[int] = total_nodes
        self.current_view: int = 0
        self.votes: Dict[str, Any] = {}
        self.decision: Optional[Any] = None

    def propose(self, value: Any) -> Any:
        """
        Initiates a new consensus round by proposing a value.

        Resets internal state and casts a self-vote for the proposed value.
        """
        self.votes = {self.node_id: value}
        self.decision = None
        self.current_view += 1
        return value

    def receive_vote(self, from_node: str, value: Any) -> bool:
        """
        Processes an incoming vote and checks for consensus.

        Args:
            from_node: Identifier of the sender.
            value: The value voted for.

        Returns:
            True if a majority consensus is achieved, False otherwise.
        """
        if not isinstance(from_node, str) or not from_node.strip():
            raise ValueError("from_node must be a non-empty string.")

        if from_node in self.votes:
            return False

        self.votes[from_node] = value
        
        # Consensus threshold: > N/2
        majority_threshold: int = (self.total_nodes // 2) + 1
        vote_counts = Counter(self.votes.values())
        
        for val, count in vote_counts.items():
            if count >= majority_threshold:
                self.decision = val
                return True
        
        return False

    def get_decision(self) -> Optional[Any]:
        """
        Retrieves the finalized consensus value.
        """
        return self.decision

    def __repr__(self) -> str:
        return (
            f"D2BFTNode(node_id={self.node_id!r}, total_nodes={self.total_nodes}, "
            f"current_view={self.current_view}, decision={self.decision!r})"
        )