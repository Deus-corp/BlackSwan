"""
ReputationManager – Tracks the trustworthiness of peers based on fitness verification.
It assigns and updates scores, and provides a mechanism to identify trusted nodes.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("Reputation")

class ReputationManager:
    """
    Manages the reputation scores of different nodes within the network.
    Scores are updated based on the accuracy of fitness claims made by nodes
    and include a decay mechanism to allow for recovery or dynamic adjustments.
    """

    # Constants for tuning the reputation system's behavior
    DEFAULT_INITIAL_SCORE: float = 1.0
    DEFAULT_TOLERANCE: float = 0.05      # Acceptable difference between claimed and actual fitness
    PENALTY_FACTOR: float = 0.2          # Multiplier for penalty amount based on deviation
    REWARD_AMOUNT: float = 0.01          # Amount added to score for accurate claims
    DECAY_RATE: float = 0.005            # Rate at which scores return to initial_score
    MAX_SCORE: float = 2.0               # Upper bound for reputation scores
    MIN_SCORE: float = 0.0               # Lower bound for reputation scores
    TRUST_THRESHOLD: float = 0.3         # Minimum score for a node to be considered trusted

    def __init__(self, initial_score: float = DEFAULT_INITIAL_SCORE, tolerance: float = DEFAULT_TOLERANCE):
        """
        Initializes the ReputationManager with a base score and tolerance for claims.

        Args:
            initial_score (float): The default reputation score assigned to newly encountered
                                   or unknown nodes.
            tolerance (float): The maximum allowed absolute difference between a node's claimed
                               fitness and its verified actual fitness before a penalty is applied.
        """
        self.scores: Dict[str, float] = {}   # Maps node_id (e.g., public_key_hex) to its reputation score
        self.initial_score = initial_score
        self.tolerance = tolerance
        self.verified_claims = 0             # Counter for claims that were within tolerance
        self.false_claims = 0                # Counter for claims that exceeded tolerance

    def get_score(self, node_id: str) -> float:
        """
        Retrieves the current reputation score for a given node ID.
        If the node is not yet tracked, its `initial_score` is returned.

        Args:
            node_id (str): The unique identifier of the node (e.g., a peer's public key hash).

        Returns:
            float: The current reputation score of the node, or the `initial_score` if unknown.
        """
        return self.scores.get(node_id, self.initial_score)

    def update(self, node_id: str, claimed_fitness: float, actual_fitness: float) -> None:
        """
        Updates the reputation score of a node based on the accuracy of its
        fitness claim.

        A penalty is applied if the `claimed_fitness` significantly exceeds the `actual_fitness`
        (i.e., `gap > self.tolerance`). A small reward is given for accurate claims.
        Scores are clamped between `MIN_SCORE` and `MAX_SCORE`.

        Args:
            node_id (str): The unique identifier of the node whose score is to be updated.
            claimed_fitness (float): The fitness value asserted by the node.
            actual_fitness (float): The fitness value independently verified by the system.
        """
        current_score = self.get_score(node_id)
        gap = claimed_fitness - actual_fitness

        if gap > self.tolerance:
            # Scale penalty based on how much the claim exceeded the tolerance threshold
            penalty = (gap / self.tolerance) * self.PENALTY_FACTOR
            new_score = current_score - penalty
            self.false_claims += 1
            logger.warning(
                f"Node {node_id[:8]}... inflated fitness. Claimed={claimed_fitness:.4f}, Actual={actual_fitness:.4f}. "
                f"Gap={gap:.4f} (tolerance={self.tolerance:.4f}). Penalty applied, new score={new_score:.2f}"
            )
        else:
            new_score = current_score + self.REWARD_AMOUNT
            self.verified_claims += 1

        # Clamp the score within the defined minimum and maximum bounds
        self.scores[node_id] = max(self.MIN_SCORE, min(self.MAX_SCORE, new_score))

    def decay(self) -> None:
        """
        Applies a decay mechanism to all tracked node scores.
        Scores that are below the `initial_score` are slowly increased towards it
        at a rate defined by `DECAY_RATE`. This allows nodes to recover reputation
        over time.
        """
        # Iterate over a copy of keys to safely modify the dictionary during iteration
        for node_id in list(self.scores.keys()):
            if self.scores[node_id] < self.initial_score:
                # Slowly increase score towards the initial_score, but not exceeding it
                self.scores[node_id] = min(self.initial_score, self.scores[node_id] + self.DECAY_RATE)
            # Optional: Add logic to decay scores above initial_score too,
            # to prevent unbounded growth if desired.
            # elif self.scores[node_id] > self.initial_score:
            #     self.scores[node_id] = max(self.initial_score, self.scores[node_id] - self.DECAY_RATE)

    def is_trusted(self, node_id: str) -> bool:
        """
        Determines if a node is considered trusted based on its current reputation score.

        Args:
            node_id (str): The unique identifier of the node.

        Returns:
            bool: True if the node's score is at or above the `TRUST_THRESHOLD`, False otherwise.
        """
        return self.get_score(node_id) >= self.TRUST_THRESHOLD

    def stats(self) -> Dict[str, Any]:
        """
        Provides various statistics about the current state of the reputation system.

        Returns:
            Dict[str, Any]: A dictionary containing key metrics:
                            - `verified_claims`: Total number of accurate claims.
                            - `false_claims`: Total number of claims that exceeded tolerance.
                            - `peer_count`: Number of distinct nodes currently being tracked.
                            - `average_score`: The average reputation score across all tracked peers.
        """
        num_peers = len(self.scores)
        return {
            "verified_claims": self.verified_claims,
            "false_claims": self.false_claims,
            "peer_count": num_peers,
            "average_score": sum(self.scores.values()) / num_peers if num_peers > 0 else 0.0
        }
