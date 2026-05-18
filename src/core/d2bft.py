"""
Минимальный прототип D2BFT консенсуса.
Узлы голосуют за значение, консенсус достигается при 2/3 голосов.
"""
from typing import Any, Dict, Optional

class D2BFTNode:
    """
    Minimal prototype for a D2BFT consensus node.
    Nodes vote on a value. Consensus is reached when a simple majority
    (more than N/2) of votes for a specific value is accumulated.
    For `total_nodes=3`, this requires 2 votes, which is equivalent to a 2/3 majority.
    """
    def __init__(self, node_id: str, total_nodes: int = 3):
        """
        Initializes a D2BFTNode.

        Args:
            node_id: A unique identifier for this node.
            total_nodes: The total number of nodes participating in the consensus group.
                         Defaults to 3 for a minimal setup.
        """
        self.node_id: str = node_id
        self.total_nodes: int = total_nodes
        self.current_view: int = 0
        # Stores votes received in the current round: {node_id: value}
        self.votes: Dict[str, Any] = {}
        # Stores the decided value once consensus is reached
        self.decision: Optional[Any] = None

    def propose(self, value: Any) -> Any:
        """
        Proposes a value for the current consensus round.
        This action resets previous votes and the decision for a new round.
        The node implicitly votes for its own proposed value.

        Args:
            value: The value to propose.

        Returns:
            The proposed value.
        """
        self.votes = {self.node_id: value}
        self.decision = None
        return value

    def receive_vote(self, from_node: str, value: Any) -> bool:
        """
        Processes a vote received from another node.
        If the vote is new, it's added to the current collection of votes.
        Checks if a simple majority for any value has been reached, leading to a decision.

        Args:
            from_node: The identifier of the node that sent the vote.
            value: The value that `from_node` is voting for.

        Returns:
            True if a decision was reached as a result of processing this vote, False otherwise.
        """
        # Only accept the first vote from a given node for the current round
        if from_node not in self.votes:
            self.votes[from_node] = value
        
        # Count votes for each value
        count: Dict[Any, int] = {}
        for v in self.votes.values():
            count[v] = count.get(v, 0) + 1
            
        # Check for simple majority: more than N/2 votes.
        # For total_nodes=3, N//2 = 1, so `cnt > 1` means `cnt >= 2`, which is a 2/3 majority.
        for v, cnt in count.items():
            if cnt > self.total_nodes // 2:
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
