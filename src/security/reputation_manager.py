"""
ReputationManager – отслеживает честность пиров на основе проверки фитнеса.
"""
import logging
from typing import Dict

logger = logging.getLogger("Reputation")

class ReputationManager:
    def __init__(self, initial_score: float = 1.0, tolerance: float = 0.05):
        self.scores: Dict[str, float] = {}   # public_key_hex -> score
        self.initial_score = initial_score
        self.tolerance = tolerance
        self.verified_claims = 0
        self.false_claims = 0

    def get_score(self, node_id: str) -> float:
        return self.scores.get(node_id, self.initial_score)

    def update(self, node_id: str, claimed_fitness: float, actual_fitness: float):
        current = self.get_score(node_id)
        gap = claimed_fitness - actual_fitness

        if gap > self.tolerance:
            penalty = (gap / self.tolerance) * 0.2
            new_score = current - penalty
            self.false_claims += 1
            logger.warning(f"Node {node_id[:8]}... inflated fitness gap={gap:.4f}, new score={new_score:.2f}")
        else:
            new_score = current + 0.01
            self.verified_claims += 1

        self.scores[node_id] = max(0.0, min(2.0, new_score))

    def decay(self):
        """Медленно возвращает репутацию к начальному уровню."""
        for nid in list(self.scores.keys()):
            if self.scores[nid] < self.initial_score:
                self.scores[nid] += 0.005

    def is_trusted(self, node_id: str) -> bool:
        return self.get_score(node_id) >= 0.3

    def stats(self) -> dict:
        return {
            "verified_claims": self.verified_claims,
            "false_claims": self.false_claims,
            "peer_count": len(self.scores),
        }