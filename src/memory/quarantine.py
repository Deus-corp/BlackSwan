from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING, runtime_checkable
from src.memory.local_memory import MemoryRecord, LocalMemoryAPI

# Define a protocol for ReputationManager to avoid circular import issues at runtime
# and enable type checking for the dependency.
@runtime_checkable
class ReputationManagerProtocol(Protocol):
    """
    Protocol defining the expected interface for a ReputationManager.
    """
    def is_trusted(self, entity_id: str) -> bool:
        """
        Checks if the given entity ID is considered trusted.
        """
        ...

# Using TYPE_CHECKING to avoid potential circular imports at runtime
# if CryptoManager also imports from local_memory.
if TYPE_CHECKING:
    from src.security.crypto_manager import CryptoManager
    # ReputationManager is now handled by ReputationManagerProtocol

logger = logging.getLogger(__name__)

class QuarantineBuffer:
    """
    A buffer and validation layer for incoming MemoryRecords.
    It performs checks like confidence, signature verification, and sender reputation
    before deciding whether to store a record in the local memory.
    """

    # --- Configuration Constants ---
    MIN_CONFIDENCE_THRESHOLD: float = 0.3

    def __init__(self, memory_api: LocalMemoryAPI, reputation: ReputationManagerProtocol):
        """
        Initializes the QuarantineBuffer.

        Args:
            memory_api: An instance of LocalMemoryAPI to store validated records.
            reputation: An instance of ReputationManagerProtocol to check sender trustworthiness.

        Raises:
            TypeError: If `memory_api` is not `LocalMemoryAPI` or `reputation` does not conform to `ReputationManagerProtocol`.
        """
        if not isinstance(memory_api, LocalMemoryAPI):
            raise TypeError("memory_api must be an instance of LocalMemoryAPI.")
        if not isinstance(reputation, ReputationManagerProtocol):
            raise TypeError("reputation must conform to ReputationManagerProtocol.")

        self.memory: LocalMemoryAPI = memory_api
        self.reputation: ReputationManagerProtocol = reputation

    def __repr__(self) -> str:
        return f"QuarantineBuffer(memory_api={self.memory.__class__.__name__}, reputation={self.reputation.__class__.__name__})"

    async def process(self, raw: dict[str, Any]) -> bool:
        """
        Processes an incoming raw dictionary, attempts to parse it into a MemoryRecord,
        and then performs validation checks before saving it to local memory.

        Validation steps include:
        1. Parsing the raw dictionary into a MemoryRecord object.
        2. Checking the record's confidence level against `MIN_CONFIDENCE_THRESHOLD`.
        3. Verifying the record's digital signature if present.
           The signed payload is assumed to be `{"payload": record.payload, "kind": record.kind, "scope": record.scope}`.
           The public key for verification is taken from `origin_pubkey` or `originNodeId` in `record.source`.
        4. Checking the reputation of the sender (origin node/public key) using `ReputationManager`.

        Args:
            raw: The raw dictionary representing an incoming MemoryRecord.

        Returns:
            True if the record passed all checks and was successfully stored, False otherwise.

        Raises:
            TypeError: If `raw` is not a dictionary.
        """
        if not isinstance(raw, dict):
            logger.warning(f"Quarantine: Received non-dictionary raw data. Type: {type(raw)}, Data: {raw}")
            return False

        # 1. Convert to MemoryRecord object
        try:
            record: MemoryRecord = MemoryRecord(**raw)
        except Exception as e:
            logger.warning(f"Quarantine: Invalid record format received. Error: {e}, Raw data: {raw}")
            return False

        # 2. Check confidence
        if record.confidence < self.MIN_CONFIDENCE_THRESHOLD:
            logger.info(
                f"Quarantine: Discarding record {record.id} due to low confidence "
                f"({record.confidence} < {self.MIN_CONFIDENCE_THRESHOLD})."
            )
            return False

        # Determine the public key for verification and reputation checks.
        # As per CryptoManager, Public Key is often used as Node ID.
        origin_pubkey_hex: Optional[str] = record.source.get("origin_pubkey") or record.source.get("originNodeId")

        # 3. Check signature, if present
        if record.signature:
            if not origin_pubkey_hex:
                logger.warning(
                    f"Quarantine: Record {record.id} has signature but no origin_pubkey or originNodeId "
                    f"in source for verification, discarding."
                )
                return False

            # The exact payload used for signing must match what's provided for verification.
            # Assuming the signed content consists of 'payload', 'kind', and 'scope'.
            signed_data_for_verification: dict[str, Any] = {
                "payload": record.payload,
                "kind": record.kind,
                "scope": record.scope
            }
            # Import CryptoManager here to avoid circular import at module level during runtime
            # and only when verification is actually needed.
            from src.security.crypto_manager import CryptoManager
            if not CryptoManager.verify(signed_data_for_verification, record.signature, origin_pubkey_hex):
                logger.warning(
                    f"Quarantine: Signature verification failed for record {record.id} "
                    f"from {origin_pubkey_hex}. Discarding."
                )
                return False
            logger.debug(f"Quarantine: Signature verified for record {record.id} from {origin_pubkey_hex}.")

        # 4. Check sender reputation
        if origin_pubkey_hex:  # Only check reputation if an origin identifier (pubkey/node_id) is present
            if not self.reputation.is_trusted(origin_pubkey_hex):
                logger.warning(
                    f"Quarantine: Untrusted source {origin_pubkey_hex} for record {record.id}, discarding."
                )
                return False
            logger.debug(f"Quarantine: Source {origin_pubkey_hex} is trusted for record {record.id}.")
        else:
            # If no origin information, it might be a locally created record or an anonymous one.
            # Current policy implicitly trusts records without an explicit origin by skipping reputation check.
            # Depending on security requirements, this could be configured to distrust by default.
            logger.info(f"Quarantine: Record {record.id} has no origin identifier, proceeding without reputation check.")

        # 5. Mark as verified and save to memory
        record.verified = True
        await self.memory.remember(record)
        logger.info(f"Quarantine: Accepted record {record.id} from {origin_pubkey_hex or 'unknown'}.")
        return True