"""
Minimal prototype for a D2BFT (Delegated Byzantine Fault Tolerance) consensus.
Nodes vote on a value, and consensus is reached when a simple majority (more than N/2)
of votes for a specific value is accumulated. For a `total_nodes` of 3, this
requires 2 votes, which effectively represents a 2/3 majority.
"""
from typing import Any, Dict, Optional
import math # for ceil, if needed for majority calculation, but integer division is fine here.

class D2BFTNode:
    """
    Minimal prototype for a D2BFT consensus node.

    This class simulates a single node participating in a D2BFT-like consensus
    process. It allows proposing values, receiving votes from other nodes, and
    determining if a consensus decision has been reached based on a simple majority.
    """
    def __init__(self, node_id: str, total_nodes: int = 3):
        """
        Initializes a D2BFTNode.

        Args:
            node_id: A unique identifier for this node (e.g., "node_A"). Must be a non-empty string.
            total_nodes: The total number of nodes participating in the consensus
                         group. Must be a positive integer. Defaults to 3 for a minimal setup where 2 votes
                         constitute a 2/3 majority.

        Raises:
            ValueError: If node_id is invalid or total_nodes is not a positive integer.
        """
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be a non-empty string.")
        if not isinstance(total_nodes, int) or total_nodes < 1:
            raise ValueError("total_nodes must be a positive integer.")

        self.node_id: str = node_id.strip() # Strip whitespace from node_id
        self.total_nodes: int = total_nodes
        self.current_view: int = 0 # This prototype doesn't extensively use views, but keeps the concept.
        # Stores votes received in the current round: {node_id: value_voted_for}
        self.votes: Dict[str, Any] = {}
        # Stores the decided value once consensus is reached
        self.decision: Optional[Any] = None

    def propose(self, value: Any) -> Any:
        """
        Proposes a value for the current consensus round.

        This action initiates a new round by resetting previous votes and the
        decision. The node implicitly votes for its own proposed value.

        Args:
            value: The value to propose. This can be any serializable type.

        Returns:
            The proposed value.
        """
        self.votes = {self.node_id: value}  # Node votes for its own proposal
        self.decision = None
        self.current_view += 1 # Advance view for a new proposal round
        return value

    def receive_vote(self, from_node: str, value: Any) -> bool:
        """
        Processes a vote received from another node.

        If the vote is new for the current round (i.e., `from_node` hasn't
        voted yet), it's added to the current collection of votes.
        After adding the vote, it checks if a simple majority for any value
        has been reached, leading to a decision.

        A simple majority is defined as more than `total_nodes / 2` votes.
        For example, if `total_nodes=3`, `3/2 = 1.5`, so more than 1.5 votes
        means 2 or more votes. This is equivalent to `floor(N/2) + 1` or `(N // 2) + 1`.

        Args:
            from_node: The identifier of the node that sent the vote. Must be a non-empty string.
            value: The value that `from_node` is voting for.

        Returns:
            True if a decision was reached as a result of processing this vote,
            False otherwise.
        
        Raises:
            ValueError: If from_node is not a non-empty string.
        """
        if not isinstance(from_node, str) or not from_node.strip():
            raise ValueError("from_node must be a non-empty string.")
        
        # Only accept the first vote from a given node for the current round
        # and ignore votes from self if already recorded by propose()
        if from_node not in self.votes:
            self.votes[from_node] = value
        else:
            # If the node already voted, ignore subsequent votes from it in the same round
            # or if it's the current node's own vote already set by propose()
            return False
        
        # Count votes for each unique value
        count: Dict[Any, int] = {}
        for v in self.votes.values():
            count[v] = count.get(v, 0) + 1
            
        # Check for simple majority: more than N/2 votes.
        # Integer division `self.total_nodes // 2` effectively gives `floor(N/2)`.
        # So we need `cnt > floor(N/2)` which is `cnt >= floor(N/2) + 1`.
        # E.g., N=3, floor(3/2)=1. Need `cnt > 1`, i.e., `cnt >= 2`.
        # E.g., N=4, floor(4/2)=2. Need `cnt > 2`, i.e., `cnt >= 3`.
        majority_threshold = (self.total_nodes // 2) + 1 # Calculate explicit majority required votes.
        for v, cnt in count.items():
            if cnt >= majority_threshold: # Changed from > self.total_nodes // 2 to >= majority_threshold for clarity
                self.decision = v
                return True
        return False

    def get_decision(self) -> Optional[Any]:
        """
        Retrieves the current consensus decision.

        Returns:
            The value that has reached consensus, or None if no decision has been made yet.
        """
        return self.decision

    def __repr__(self) -> str:
        """
        Returns a string representation of the D2BFTNode instance.
        """
        return (
            f"D2BFTNode(node_id='{self.node_id}', total_nodes={self.total_nodes}, "
            f"current_view={self.current_view}, decision={self.decision})"
        )