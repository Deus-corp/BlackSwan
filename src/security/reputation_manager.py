"""Reputation manager for node trust scoring and fitness-claim verification."""

from __future__ import annotations

import logging
import math
from typing import Any, Final

logger = logging.getLogger("Reputation")


class ReputationManager:
    """Track peer reputation from verified and false fitness claims."""

    __slots__ = (
        "scores",
        "initial_score",
        "tolerance",
        "verified_claims",
        "false_claims",
        "updates_by_node",
    )

    DEFAULT_INITIAL_SCORE: Final[float] = 1.0
    DEFAULT_TOLERANCE: Final[float] = 0.05

    PENALTY_FACTOR: Final[float] = 0.2
    REWARD_AMOUNT: Final[float] = 0.01
    DECAY_RATE: Final[float] = 0.005

    MAX_SCORE: Final[float] = 2.0
    MIN_SCORE: Final[float] = 0.0
    TRUST_THRESHOLD: Final[float] = 0.3

    def __init__(
        self,
        initial_score: float = DEFAULT_INITIAL_SCORE,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> None:
        self.initial_score = self._clamp(
            self._safe_float(initial_score, self.DEFAULT_INITIAL_SCORE),
            self.MIN_SCORE,
            self.MAX_SCORE,
        )
        self.tolerance = max(1e-9, self._safe_float(tolerance, self.DEFAULT_TOLERANCE))

        self.scores: dict[str, float] = {}
        self.verified_claims = 0
        self.false_claims = 0
        self.updates_by_node: dict[str, int] = {}

    def get_score(self, node_id: str) -> float:
        """Return current reputation score for a node."""
        clean_node_id = self._clean_node_id(node_id)
        if not clean_node_id:
            return self.initial_score
        return self.scores.get(clean_node_id, self.initial_score)

    def update(self, node_id: str, claimed_fitness: float, actual_fitness: float) -> None:
        """Update reputation based on claimed-vs-actual fitness accuracy."""
        clean_node_id = self._clean_node_id(node_id)
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        claimed = self._safe_float(claimed_fitness, 0.0)
        actual = self._safe_float(actual_fitness, 0.0)

        current_score = self.get_score(clean_node_id)
        gap = claimed - actual

        if gap > self.tolerance:
            penalty = min(self.MAX_SCORE, (gap / self.tolerance) * self.PENALTY_FACTOR)
            new_score = current_score - penalty
            self.false_claims += 1

            logger.warning(
                "Node %s inflated fitness. claimed=%.4f actual=%.4f gap=%.4f penalty=%.4f",
                clean_node_id[:8],
                claimed,
                actual,
                gap,
                penalty,
            )
        else:
            new_score = current_score + self.REWARD_AMOUNT
            self.verified_claims += 1
            logger.debug(
                "Node %s fitness claim verified. claimed=%.4f actual=%.4f",
                clean_node_id[:8],
                claimed,
                actual,
            )

        self.scores[clean_node_id] = self._clamp(new_score, self.MIN_SCORE, self.MAX_SCORE)
        self.updates_by_node[clean_node_id] = self.updates_by_node.get(clean_node_id, 0) + 1

    def penalize(self, node_id: str, amount: float = PENALTY_FACTOR, reason: str = "") -> float:
        """Apply a manual reputation penalty and return the new score."""
        clean_node_id = self._clean_node_id(node_id)
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        penalty = max(0.0, self._safe_float(amount, self.PENALTY_FACTOR))
        new_score = self._clamp(self.get_score(clean_node_id) - penalty, self.MIN_SCORE, self.MAX_SCORE)
        self.scores[clean_node_id] = new_score
        self.updates_by_node[clean_node_id] = self.updates_by_node.get(clean_node_id, 0) + 1

        logger.warning(
            "Node %s reputation penalized by %.4f. reason=%s new_score=%.4f",
            clean_node_id[:8],
            penalty,
            reason or "manual",
            new_score,
        )
        return new_score

    def reward(self, node_id: str, amount: float = REWARD_AMOUNT, reason: str = "") -> float:
        """Apply a manual reputation reward and return the new score."""
        clean_node_id = self._clean_node_id(node_id)
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        reward = max(0.0, self._safe_float(amount, self.REWARD_AMOUNT))
        new_score = self._clamp(self.get_score(clean_node_id) + reward, self.MIN_SCORE, self.MAX_SCORE)
        self.scores[clean_node_id] = new_score
        self.updates_by_node[clean_node_id] = self.updates_by_node.get(clean_node_id, 0) + 1

        logger.debug(
            "Node %s reputation rewarded by %.4f. reason=%s new_score=%.4f",
            clean_node_id[:8],
            reward,
            reason or "manual",
            new_score,
        )
        return new_score

    def decay(self) -> None:
        """Gradually pull tracked scores toward initial_score."""
        for node_id, score in list(self.scores.items()):
            if score < self.initial_score:
                self.scores[node_id] = min(self.initial_score, score + self.DECAY_RATE)
            elif score > self.initial_score:
                self.scores[node_id] = max(self.initial_score, score - self.DECAY_RATE)

    def is_trusted(self, node_id: str) -> bool:
        """Return True if node score meets trust threshold."""
        return self.get_score(node_id) >= self.TRUST_THRESHOLD

    def trusted_nodes(self) -> list[str]:
        """Return tracked node IDs currently above trust threshold."""
        return sorted(node_id for node_id in self.scores if self.is_trusted(node_id))

    def stats(self) -> dict[str, Any]:
        """Return aggregate reputation metrics."""
        peer_count = len(self.scores)
        average_score = sum(self.scores.values()) / peer_count if peer_count else self.initial_score

        return {
            "verified_claims": self.verified_claims,
            "false_claims": self.false_claims,
            "peer_count": peer_count,
            "trusted_peer_count": len(self.trusted_nodes()),
            "average_score": average_score,
            "initial_score": self.initial_score,
            "trust_threshold": self.TRUST_THRESHOLD,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize reputation state."""
        return {
            "scores": dict(self.scores),
            "initial_score": self.initial_score,
            "tolerance": self.tolerance,
            "verified_claims": self.verified_claims,
            "false_claims": self.false_claims,
            "updates_by_node": dict(self.updates_by_node),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Load reputation state from a dictionary."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")

        raw_scores = data.get("scores", {})
        self.scores = {
            self._clean_node_id(node_id): self._clamp(self._safe_float(score, self.initial_score), self.MIN_SCORE, self.MAX_SCORE)
            for node_id, score in raw_scores.items()
            if self._clean_node_id(node_id)
        } if isinstance(raw_scores, dict) else {}

        self.initial_score = self._clamp(
            self._safe_float(data.get("initial_score"), self.initial_score),
            self.MIN_SCORE,
            self.MAX_SCORE,
        )
        self.tolerance = max(1e-9, self._safe_float(data.get("tolerance"), self.tolerance))
        self.verified_claims = max(0, int(self._safe_float(data.get("verified_claims"), 0)))
        self.false_claims = max(0, int(self._safe_float(data.get("false_claims"), 0)))

        raw_updates = data.get("updates_by_node", {})
        self.updates_by_node = {
            self._clean_node_id(node_id): max(0, int(self._safe_float(count, 0)))
            for node_id, count in raw_updates.items()
            if self._clean_node_id(node_id)
        } if isinstance(raw_updates, dict) else {}

    @staticmethod
    def _clean_node_id(node_id: str) -> str:
        return str(node_id or "").strip()

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))