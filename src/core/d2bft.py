"""
Minimal prototype for a D2BFT (Delegated Byzantine Fault Tolerance) consensus.
Nodes vote on a value, and consensus is reached when a simple majority (more than N/2)
of votes for a specific value is accumulated. For a `total_nodes` of 3, this
requires 2 votes, which effectively represents a 2/3 majority.
"""
from typing import Any, Dict, Optional

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
            node_id: A unique identifier for this node (e.g., "node_A").
            total_nodes: The total number of nodes participating in the consensus
                         group. Defaults to 3 for a minimal setup where 2 votes
                         constitute a 2/3 majority.
        """
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node_id must be a non-empty string.")
        if not isinstance(total_nodes, int) or total_nodes < 1:
            raise ValueError("total_nodes must be a positive integer.")

        self.node_id: str = node_id
        self.total_nodes: int = total_nodes
        self.current_view: int = 0
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
        means 2 or more votes.

        Args:
            from_node: The identifier of the node that sent the vote.
            value: The value that `from_node` is voting for.

        Returns:
            True if a decision was reached as a result of processing this vote,
            False otherwise.
        """
        # Only accept the first vote from a given node for the current round
        if from_node not in self.votes:
            self.votes[from_node] = value
        else:
            # If the node already voted, ignore subsequent votes from it in the same round
            return False
        
        # Count votes for each unique value
        count: Dict[Any, int] = {}
        for v in self.votes.values():
            count[v] = count.get(v, 0) + 1
            
        # Check for simple majority: more than N/2 votes.
        # Integer division `self.total_nodes // 2` effectively gives `floor(N/2)`.
        # So we need `cnt > floor(N/2)`.
        # E.g., N=3, floor(3/2)=1. Need `cnt > 1`, i.e., `cnt >= 2`.
        # E.g., N=4, floor(4/2)=2. Need `cnt > 2`, i.e., `cnt >= 3`.
        majority_threshold = self.total_nodes // 2
        for v, cnt in count.items():
            if cnt > majority_threshold:
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