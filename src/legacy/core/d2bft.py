"""Minimal delegated Byzantine-style majority voting helper.

This module intentionally implements a small deterministic vote collector, not a
full production D2BFT protocol. It is useful for tests, local coordination, and
simple swarm decisions where each node may cast one vote per view.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Final, Optional


class D2BFTNode:
    """Single-node view of a delegated majority-vote consensus round."""

    __slots__ = ("node_id", "total_nodes", "current_view", "votes", "decision")

    def __init__(self, node_id: str, total_nodes: int = 3) -> None:
        clean_node_id = self._require_node_id(node_id)
        clean_total_nodes = int(total_nodes)

        if clean_total_nodes < 1:
            raise ValueError("total_nodes must be a positive integer")

        self.node_id: Final[str] = clean_node_id
        self.total_nodes: Final[int] = clean_total_nodes
        self.current_view: int = 0
        self.votes: dict[str, Any] = {}
        self.decision: Optional[Any] = None

    @property
    def majority_threshold(self) -> int:
        """Return the strict majority threshold for this consensus group."""
        return (self.total_nodes // 2) + 1

    def propose(self, value: Any) -> Any:
        """Start a new view and cast the local node's vote."""
        self.current_view += 1
        self.decision = None
        self.votes = {self.node_id: value}
        self._update_decision()
        return value

    def receive_vote(self, from_node: str, value: Any) -> bool:
        """Record a vote and return True only when this call reaches consensus."""
        voter = self._require_node_id(from_node)

        if voter in self.votes:
            return False

        if len(self.votes) >= self.total_nodes:
            return False

        was_decided = self.decision is not None
        self.votes[voter] = value
        self._update_decision()

        return self.decision is not None and not was_decided

    def get_decision(self) -> Optional[Any]:
        """Return the finalized value, if consensus has been reached."""
        return self.decision

    def reset(self) -> None:
        """Clear votes and decision while keeping the current view number."""
        self.votes.clear()
        self.decision = None

    def vote_count(self, value: Any) -> int:
        """Return how many votes currently support value."""
        return Counter(self.votes.values()).get(value, 0)

    def has_vote_from(self, node_id: str) -> bool:
        """Return True when node_id has already voted in the current view."""
        voter = str(node_id or "").strip()
        return bool(voter and voter in self.votes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the local consensus state."""
        return {
            "node_id": self.node_id,
            "total_nodes": self.total_nodes,
            "current_view": self.current_view,
            "votes": dict(self.votes),
            "decision": self.decision,
            "majority_threshold": self.majority_threshold,
        }

    def _update_decision(self) -> None:
        if self.decision is not None:
            return

        for value, count in Counter(self.votes.values()).items():
            if count >= self.majority_threshold:
                self.decision = value
                return

    @staticmethod
    def _require_node_id(node_id: str) -> str:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id must be a non-empty string")
        return clean_node_id

    def __repr__(self) -> str:
        return (
            f"D2BFTNode(node_id={self.node_id!r}, total_nodes={self.total_nodes}, "
            f"current_view={self.current_view}, votes={len(self.votes)}, "
            f"decision={self.decision!r})"
        )