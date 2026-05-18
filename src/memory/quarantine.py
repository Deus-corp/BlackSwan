# src/memory/quarantine.py
"""
Quarantine buffer for incoming MemoryRecords.
Validates signature, sender reputation, and confidence before storing.
"""
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING # For type hinting imports that might cause circular dependency at runtime
from src.memory.local_memory import MemoryRecord, LocalMemoryAPI

# Using TYPE_CHECKING to avoid potential circular imports at runtime
# if CryptoManager or ReputationManager also import from local_memory.
if TYPE_CHECKING:
    from src.security.crypto_manager import CryptoManager
    from src.security.reputation_manager import ReputationManager

logger = logging.getLogger(__name__)

class QuarantineBuffer:
    """
    A buffer and validation layer for incoming MemoryRecords.
    It performs checks like confidence, signature verification, and sender reputation
    before deciding whether to store a record in the local memory.
    """

    def __init__(self, memory_api: LocalMemoryAPI, reputation: 'ReputationManager'):
        """
        Initializes the QuarantineBuffer.

        Args:
            memory_api: An instance of LocalMemoryAPI to store validated records.
            reputation: An instance of ReputationManager to check sender trustworthiness.
        """
        self.memory: LocalMemoryAPI = memory_api
        self.reputation: 'ReputationManager' = reputation
        # CryptoManager is used statically, so no need to pass an instance.

    async def process(self, raw: Dict[str, Any]) -> bool:
        """
        Processes an incoming raw dictionary, attempts to parse it into a MemoryRecord,
        and then performs validation checks before saving it to local memory.

        Validation steps include:
        1. Parsing the raw dictionary into a MemoryRecord object.
        2. Checking the record's confidence level.
        3. Verifying the record's digital signature if present.
           The signed payload is assumed to be `{"payload": record.payload, "kind": record.kind, "scope": record.scope}`.
           The public key for verification is taken from `origin_pubkey` or `originNodeId` in `record.source`.
        4. Checking the reputation of the sender (origin node/public key).

        Args:
            raw: The raw dictionary representing an incoming MemoryRecord.

        Returns:
            True if the record passed all checks and was successfully stored, False otherwise.
        """
        # 1. Convert to MemoryRecord object
        try:
            record = MemoryRecord(**raw)
        except Exception as e:
            logger.warning(f"Quarantine: Invalid record format received. Error: {e}, Raw data: {raw}")
            return False

        # 2. Check confidence
        if record.confidence < 0.3: # Hardcoded threshold, could be configurable
            logger.info(f"Quarantine: Discarding record {record.id} due to low confidence ({record.confidence}).")
            return False

        # Determine the public key for verification and reputation checks.
        # As per CryptoManager, Public Key is often used as Node ID.
        origin_pubkey_hex = record.source.get("origin_pubkey") or record.source.get("originNodeId")

        # 3. Check signature, if present
        if record.signature:
            if not origin_pubkey_hex:
                logger.warning(f"Quarantine: Record {record.id} has signature but no origin_pubkey or originNodeId in source, discarding.")
                return False

            # The exact payload used for signing must match what's provided for verification.
            # Assuming the signed content consists of 'payload', 'kind', and 'scope'.
            signed_data_for_verification = {
                "payload": record.payload,
                "kind": record.kind,
                "scope": record.scope
            }
            # Import CryptoManager here to avoid circular import at module level during runtime
            from src.security.crypto_manager import CryptoManager
            if not CryptoManager.verify(signed_data_for_verification, record.signature, origin_pubkey_hex):
                logger.warning(f"Quarantine: Signature verification failed for record {record.id} from {origin_pubkey_hex}.")
                return False
            logger.debug(f"Quarantine: Signature verified for record {record.id} from {origin_pubkey_hex}.")

        # 4. Check sender reputation
        if origin_pubkey_hex: # Only check reputation if an origin identifier (pubkey/node_id) is present
            if not self.reputation.is_trusted(origin_pubkey_hex):
                logger.warning(f"Quarantine: Untrusted source {origin_pubkey_hex} for record {record.id}, discarding.")
                return False
            logger.debug(f"Quarantine: Source {origin_pubkey_hex} is trusted for record {record.id}.")
        else:
            # If no origin information, it might be a local record or anonymous.
            # Depending on policy, such records might be automatically trusted or distrusted.
            # Current logic proceeds if no origin, effectively trusting implicitly (no reputation check performed).
            logger.info(f"Quarantine: Record {record.id} has no origin identifier, proceeding without reputation check.")

        # 5. Mark as verified and save to memory
        record.verified = True
        await self.memory.remember(record)
        logger.info(f"Quarantine: Accepted record {record.id} from {origin_pubkey_hex or 'unknown'}.")
        return True