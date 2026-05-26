from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Final

logger = logging.getLogger(__name__)

DEFAULT_QUORUM: Final[int] = 3


@dataclass(slots=True)
class Proposal:
    """A trade proposal requiring signatures from multiple swarm nodes."""

    proposer_node_id: str
    action: str
    amount: float
    symbol: str
    signatures: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.proposer_node_id = self._require_text(self.proposer_node_id, "proposer_node_id")
        self.action = self._require_text(self.action, "action").lower()
        self.symbol = self._require_text(self.symbol, "symbol").upper()
        self.amount = float(self.amount)

        if self.amount <= 0:
            raise ValueError("amount must be positive")

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} cannot be empty")
        return text

    def sign(self, node_id: str, signature: str) -> None:
        """Add or replace a node signature for this proposal."""
        clean_node_id = self._require_text(node_id, "node_id")
        clean_signature = self._require_text(signature, "signature")
        self.signatures[clean_node_id] = clean_signature

    def is_approved(self, quorum: int = DEFAULT_QUORUM) -> bool:
        """Return True when the number of unique signatures reaches quorum."""
        required = int(quorum)
        if required <= 0:
            raise ValueError("quorum must be positive")
        return len(self.signatures) >= required

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proposal for gossip transmission or storage."""
        return {
            "proposer_node_id": self.proposer_node_id,
            "action": self.action,
            "amount": self.amount,
            "symbol": self.symbol,
            "signatures": dict(self.signatures),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        """Deserialize a proposal from a dictionary payload."""
        proposal = cls(
            proposer_node_id=str(data.get("proposer_node_id", "")),
            action=str(data.get("action", "")),
            amount=float(data.get("amount", 0.0)),
            symbol=str(data.get("symbol", "")),
        )

        raw_signatures = data.get("signatures", {})
        if isinstance(raw_signatures, dict):
            for node_id, signature in raw_signatures.items():
                proposal.sign(str(node_id), str(signature))

        return proposal


class ConsensusManager:
    """Engine managing proposal lifecycle and threshold consensus."""

    __slots__ = ("node_id", "quorum")

    def __init__(self, node_id: str, quorum: int = DEFAULT_QUORUM) -> None:
        self.node_id: Final[str] = Proposal._require_text(node_id, "node_id")
        self.quorum: Final[int] = int(quorum)

        if self.quorum <= 0:
            raise ValueError("quorum must be positive")

        logger.info("ConsensusManager initialized for node %s quorum=%s", self.node_id, self.quorum)

    def create_proposal(self, action: str, amount: float, symbol: str) -> Proposal:
        """Create a new proposal originating from this node."""
        return Proposal(
            proposer_node_id=self.node_id,
            action=action,
            amount=amount,
            symbol=symbol,
        )

    def process_signature(self, proposal: Proposal, node_id: str, signature: str) -> bool:
        """Apply a signature and return True if the proposal reaches quorum."""
        if not isinstance(proposal, Proposal):
            raise TypeError("proposal must be a Proposal instance")

        proposal.sign(node_id, signature)
        is_approved = proposal.is_approved(self.quorum)

        if is_approved:
            logger.info(
                "Proposal reached quorum: proposer=%s action=%s symbol=%s signatures=%s/%s",
                proposal.proposer_node_id,
                proposal.action,
                proposal.symbol,
                len(proposal.signatures),
                self.quorum,
            )

        return is_approved