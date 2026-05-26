from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from src.memory.local_memory import LocalMemoryAPI, MemoryRecord

logger = logging.getLogger(__name__)


@runtime_checkable
class ReputationManagerProtocol(Protocol):
    """Expected reputation manager interface."""

    def is_trusted(self, entity_id: str) -> bool:
        ...


class QuarantineBuffer:
    """Validate incoming MemoryRecords before storing them in local memory."""

    __slots__ = ("memory", "reputation", "min_confidence")

    MIN_CONFIDENCE_THRESHOLD = 0.3

    def __init__(
        self,
        memory_api: LocalMemoryAPI,
        reputation: ReputationManagerProtocol,
        *,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
    ) -> None:
        if not isinstance(memory_api, LocalMemoryAPI):
            raise TypeError("memory_api must be an instance of LocalMemoryAPI")
        if not isinstance(reputation, ReputationManagerProtocol):
            raise TypeError("reputation must conform to ReputationManagerProtocol")

        self.memory = memory_api
        self.reputation = reputation
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))

    def __repr__(self) -> str:
        return (
            f"QuarantineBuffer(memory_api={type(self.memory).__name__}, "
            f"reputation={type(self.reputation).__name__}, "
            f"min_confidence={self.min_confidence:.2f})"
        )

    async def process(self, raw: dict[str, Any]) -> bool:
        """Parse, validate, verify, and store a memory record."""
        if not isinstance(raw, dict):
            logger.warning("Quarantine rejected non-dict payload: %s", type(raw).__name__)
            return False

        try:
            record = MemoryRecord.model_validate(raw)
        except Exception as exc:
            logger.warning("Quarantine rejected invalid record format: %s", exc)
            return False

        if record.expired:
            logger.info("Quarantine discarded expired record %s.", record.id)
            return False

        if record.confidence < self.min_confidence:
            logger.info(
                "Quarantine discarded record %s due to low confidence %.3f < %.3f.",
                record.id,
                record.confidence,
                self.min_confidence,
            )
            return False

        origin_id = self._origin_id(record)

        if record.signature and not self._verify_signature(record, origin_id):
            return False

        if origin_id and not self._is_trusted(origin_id):
            logger.warning("Quarantine rejected untrusted source %s for record %s.", origin_id, record.id)
            return False

        if not origin_id:
            logger.debug("Quarantine accepted anonymous record %s without reputation check.", record.id)

        record.verified = bool(record.signature or origin_id)
        await self.memory.remember(record)

        logger.info("Quarantine accepted record %s from %s.", record.id, origin_id or "anonymous")
        return True

    def _verify_signature(self, record: MemoryRecord, origin_id: str | None) -> bool:
        if not origin_id:
            logger.warning("Quarantine rejected signed record %s without origin identity.", record.id)
            return False

        try:
            from src.security.crypto_manager import CryptoManager

            payload = {
                "payload": record.payload,
                "kind": record.kind,
                "scope": record.scope,
                "payload_hash": record.payload_hash,
            }
            verified = bool(CryptoManager.verify(payload, str(record.signature), origin_id))
        except Exception as exc:
            logger.warning("Quarantine signature verification error for record %s: %s", record.id, exc)
            return False

        if not verified:
            logger.warning("Quarantine rejected record %s: signature verification failed.", record.id)
            return False

        return True

    def _is_trusted(self, origin_id: str) -> bool:
        try:
            return bool(self.reputation.is_trusted(origin_id))
        except Exception as exc:
            logger.warning("Reputation check failed for source %s: %s", origin_id, exc)
            return False

    @staticmethod
    def _origin_id(record: MemoryRecord) -> str | None:
        source = record.source if isinstance(record.source, dict) else {}

        for key in ("origin_pubkey", "originNodeId", "originPeerId", "sender_pubkey", "sender_node_id"):
            value = str(source.get(key, "") or "").strip()
            if value:
                return value

        return None