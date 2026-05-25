from __future__ import annotations

import logging
from typing import Any, Dict, Protocol, runtime_checkable, TYPE_CHECKING

from src.memory.local_memory import LocalMemoryAPI, MemoryRecord

if TYPE_CHECKING:
    from src.security.crypto_manager import CryptoManager

logger = logging.getLogger(__name__)

@runtime_checkable
class ReputationManagerProtocol(Protocol):
    """Protocol defining the expected interface for a ReputationManager."""

    def is_trusted(self, entity_id: str) -> bool:
        """Checks if the given entity ID is considered trusted."""
        ...

class QuarantineBuffer:
    """
    A buffer and validation layer for incoming MemoryRecords.
    Performs confidence, signature, and reputation checks before memory ingestion.
    """

    __slots__ = ("memory", "reputation")

    MIN_CONFIDENCE_THRESHOLD: float = 0.3

    def __init__(self, memory_api: LocalMemoryAPI, reputation: ReputationManagerProtocol) -> None:
        """
        Initializes the QuarantineBuffer with required dependencies.

        Args:
            memory_api: The local memory storage interface.
            reputation: The reputation manager for source verification.
        """
        if not isinstance(memory_api, LocalMemoryAPI):
            raise TypeError("memory_api must be an instance of LocalMemoryAPI.")
        if not isinstance(reputation, ReputationManagerProtocol):
            raise TypeError("reputation must conform to ReputationManagerProtocol.")

        self.memory = memory_api
        self.reputation = reputation

    def __repr__(self) -> str:
        return f"QuarantineBuffer(memory_api={type(self.memory).__name__}, reputation={type(self.reputation).__name__})"

    async def process(self, raw: Dict[str, Any]) -> bool:
        """
        Parses, validates, and stores a memory record.

        Args:
            raw: The raw dictionary containing memory record data.

        Returns:
            bool: True if accepted and stored, False otherwise.
        """
        if not isinstance(raw, dict):
            logger.warning("Quarantine: Received non-dictionary raw data: %s", type(raw))
            return False

        try:
            record = MemoryRecord(**raw)
        except (ValueError, TypeError) as e:
            logger.warning("Quarantine: Invalid record format: %s", e)
            return False

        if record.confidence < self.MIN_CONFIDENCE_THRESHOLD:
            logger.info("Quarantine: Discarding record %s due to low confidence (%s)", record.id, record.confidence)
            return False

        origin_id: str | None = record.source.get("origin_pubkey") or record.source.get("originNodeId")

        # Signature Verification
        if record.signature:
            if not origin_id:
                logger.warning("Quarantine: Record %s has signature but no origin identity.", record.id)
                return False

            from src.security.crypto_manager import CryptoManager

            payload = {"payload": record.payload, "kind": record.kind, "scope": record.scope}

            if not CryptoManager.verify(payload, record.signature, origin_id):
                logger.warning("Quarantine: Signature verification failed for record %s", record.id)
                return False

        # Reputation Check
        if origin_id:
            if not self.reputation.is_trusted(origin_id):
                logger.warning("Quarantine: Untrusted source %s for record %s", origin_id, record.id)
                return False
        else:
            logger.info("Quarantine: Record %s has no origin, skipping reputation check.", record.id)

        record.verified = True
        await self.memory.remember(record)
        logger.info("Quarantine: Accepted record %s from %s", record.id, origin_id or "anonymous")
        return True