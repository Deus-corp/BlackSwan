"""
ReputationManager tracks node trustworthiness based on fitness verification.
It assigns and updates scores, and provides a mechanism to identify trusted nodes.
"""
import logging
from typing import Dict, Any, Final

logger: logging.Logger = logging.getLogger("Reputation")

class ReputationManager:
    """
    Manages the reputation scores of network nodes.

    Scores are updated based on the accuracy of fitness claims and include
    a decay mechanism to allow for dynamic adjustments over time.
    """

    __slots__ = ("scores", "initial_score", "tolerance", "verified_claims", "false_claims")

    DEFAULT_INITIAL_SCORE: Final[float] = 1.0
    DEFAULT_TOLERANCE: Final[float] = 0.05
    PENALTY_FACTOR: Final[float] = 0.2
    REWARD_AMOUNT: Final[float] = 0.01
    DECAY_RATE: Final[float] = 0.005
    MAX_SCORE: Final[float] = 2.0
    MIN_SCORE: Final[float] = 0.0
    TRUST_THRESHOLD: Final[float] = 0.3

    def __init__(self, initial_score: float = DEFAULT_INITIAL_SCORE, tolerance: float = DEFAULT_TOLERANCE) -> None:
        """Initialize the manager with default constraints."""
        self.scores: Dict[str, float] = {}
        self.initial_score: float = initial_score
        self.tolerance: float = tolerance
        self.verified_claims: int = 0
        self.false_claims: int = 0

    def get_score(self, node_id: str) -> float:
        """Retrieve the current reputation score for a node."""
        return self.scores.get(node_id, self.initial_score)

    def update(self, node_id: str, claimed_fitness: float, actual_fitness: float) -> None:
        """Update reputation based on claim accuracy vs verification."""
        current_score: float = self.get_score(node_id)
        gap: float = claimed_fitness - actual_fitness

        if gap > self.tolerance:
            penalty: float = (gap / self.tolerance) * self.PENALTY_FACTOR
            new_score: float = current_score - penalty
            self.false_claims += 1
            logger.warning(
                f"Node {node_id[:8]} inflated fitness. Claimed={claimed_fitness:.4f}, "
                f"Actual={actual_fitness:.4f}. Gap={gap:.4f}. Penalty applied."
            )
        else:
            new_score = current_score + self.REWARD_AMOUNT
            self.verified_claims += 1

        self.scores[node_id] = max(self.MIN_SCORE, min(self.MAX_SCORE, new_score))

    def decay(self) -> None:
        """Gradually pull sub-initial scores back toward initial_score."""
        for node_id, score in self.scores.items():
            if score < self.initial_score:
                self.scores[node_id] = min(self.initial_score, score + self.DECAY_RATE)

    def is_trusted(self, node_id: str) -> bool:
        """Check if a node meets the reputation threshold."""
        return self.get_score(node_id) >= self.TRUST_THRESHOLD

    def stats(self) -> Dict[str, Any]:
        """Return current system metrics."""
        num_peers: int = len(self.scores)
        avg: float = sum(self.scores.values()) / num_peers if num_peers > 0 else 0.0
        return {
            "verified_claims": self.verified_claims,
            "false_claims": self.false_claims,
            "peer_count": num_peers,
            "average_score": avg
        }