import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Union, Final

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.core.crdt_layer import CRDTStorage, GenomeCRDT
from src.core.gossip_filter import GossipFilter
from src.security.gossip_envelope import GossipEnvelope, b64decode, verify_envelope
from swarm_config import config

logger = logging.getLogger(__name__)


# Forward declaration for QuarantineBuffer to avoid circular imports at module level
class QuarantineBuffer:
    """
    Dummy class for type hinting `QuarantineBuffer`, which is imported conditionally
    to prevent circular dependencies with `memory_api` or `reputation` modules.
    """

    def __init__(self, memory_api: Any, reputation: Any) -> None:
        """
        Initializes the dummy QuarantineBuffer.

        Args:
            memory_api (Any): A placeholder for the memory API object.
            reputation (Any): A placeholder for the reputation system object.
        """
        pass

    async def process(self, genome: Dict[str, Any]) -> None:
        """
        Processes a genome, dummy implementation.

        Args:
            genome (Dict[str, Any]): The genome data to process.
        """
        pass


class CRDTAdapter:
    """
    Adapter integrating GenomeCRDT with SQLite persistence.

    This class provides an interface compatible with `node_agent.py`,
    enabling the use of a distributed CRDT data structure for genome management.

    The adapter is responsible for:
    - Initializing and interacting with GenomeCRDT for storing and managing genomes.
    - Processing incoming messages, including `GossipEnvelope`s, signature verification,
      and applying filters.
    - Integrating with a quarantine system for suspicious memory facts.
    - Managing special records like nonces and heartbeats.
    - Providing methods to query CRDT state, deltas, and top genomes.
    """

    # Constants for special record types
    NONCE_RECORD_TYPE: Final[str] = "nonce_record"
    HEARTBEAT_RECORD_TYPE: Final[str] = "heartbeat"
    MEMORY_FACT_PAYLOAD_TYPE: Final[str] = "memory.fact"
    GOSSIP_DOMAIN_V1: Final[str] = "blackswan-gossip-v1"

    node_id: str
    storage: CRDTStorage
    crdt: GenomeCRDT
    _seen_nonces: Dict[str, Set[str]]  # Tracks nonces for each sender_node_id to prevent replay attacks
    _last_seq: Dict[str, int]  # Tracks last sequence number for each sender_node_id for ordered delivery
    memory_api: Optional[Any]  # Can be more specific if a Protocol is defined for MemoryAPI
    reputation: Optional[Any]  # Can be more specific if a Protocol is defined for ReputationSystem
    gossip_filter: GossipFilter
    quarantine: Optional[QuarantineBuffer]

    def __init__(
        self,
        node_id: str,
        memory_api: Optional[Any] = None,
        reputation: Optional[Any] = None,
        db_path: Optional[str] = None,
    ) -> None:
        """
        Initializes the CRDTAdapter.

        Args:
            node_id (str): The unique identifier of the current node.
            memory_api (Optional[Any]): The memory API object, if available.
                                        Used for interaction with the memory module
                                        (e.g., for quarantine).
            reputation (Optional[Any]): The reputation system object, if available.
                                        Used for assessing message trustworthiness
                                        (e.g., for quarantine).
            db_path (Optional[str]): Path to the SQLite database file.
                                      If None, `config.crdt_db_path` is used.
        """
        self.node_id = node_id
        final_db_path: str = db_path or config.crdt_db_path
        self.storage = CRDTStorage(final_db_path)
        self.crdt = GenomeCRDT(node_id, storage=self.storage)
        self._seen_nonces = {}
        self._last_seq = {}
        self.memory_api = memory_api
        self.reputation = reputation
        self.gossip_filter = GossipFilter(max_clock_skew_ms=config.gossip_max_clock_skew_ms)
        self.quarantine = None

        if memory_api and reputation:
            # Import QuarantineBuffer here to avoid circular dependencies
            # if memory_api or reputation themselves depend on CRDTAdapter.
            from src.memory.quarantine import QuarantineBuffer  # pylint: disable=import-outside-toplevel

            self.quarantine = QuarantineBuffer(memory_api, reputation)

    async def add_genome(self, genome: Dict[str, Any]) -> str:
        """
        Adds a genome or processes an incoming gossip envelope, saving the data to the CRDT.

        This method intelligently determines the type of incoming data:
        1.  `GossipEnvelope`: Verifies the signature (if enabled), applies filters,
            handles quarantine for memory facts, then extracts and adds the payload.
        2.  Custom data types (e.g., heartbeat, meta_command): Stores them as is,
            if they contain a "type" field.
        3.  Standard genome: Transforms into a canonical format and stores.

        Args:
            genome (Dict[str, Any]): The genome or gossip envelope (as a dictionary)
                                     to be added.

        Returns:
            str: The Globally Unique Identifier (GID) of the added genome.
                 Returns an empty string if the genome was invalid, rejected by
                 the filter, or signature verification failed.
        """
        sender_id: str = self.node_id  # Default sender for logging, updated if it's a gossip envelope
        processed_payload: Dict[str, Any] = genome  # Payload might be updated from envelope

        # --- Process Gossip Envelope ---
        if isinstance(genome, dict) and genome.get("domain") == self.GOSSIP_DOMAIN_V1:
            try:
                envelope = GossipEnvelope(**genome)
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid gossip envelope format, discarding: {e} | Envelope data: {genome}")
                return ""

            sender_id = envelope.sender_node_id  # Update sender_id for logging

            # Apply gossip filter (e.g., anti-entropy, deduplication based on sequence/nonce/timestamp)
            if not self.gossip_filter.check(
                sender_node_id=envelope.sender_node_id,
                nonce=envelope.nonce,
                seq_no=envelope.seq_no,
                timestamp_ms=envelope.timestamp_ms,
                ttl_ms=envelope.ttl_ms,
            ):
                logger.warning(
                    f"Gossip message from {envelope.sender_node_id} "
                    f"with nonce {envelope.nonce} rejected by filter."
                )
                return ""

            if config.gossip_signing_enabled:
                # Decode public key from base64
                try:
                    sender_pubkey_bytes: bytes = b64decode(envelope.sender_pubkey)
                    pubkey: Ed25519PublicKey = Ed25519PublicKey.from_public_bytes(sender_pubkey_bytes)
                except Exception as e:  # Catch broader exceptions for key decoding issues
                    logger.warning(f"Invalid public key in envelope from {sender_id}, discarding: {e}")
                    return ""

                now_ms: int = int(time.time() * 1000)
                seen_nonces = self._seen_nonces.setdefault(envelope.sender_node_id, set())
                last_seq = self._last_seq.get(envelope.sender_node_id, -1)

                valid, reason = verify_envelope(envelope, pubkey, seen_nonces, last_seq, now_ms)
                if not valid:
                    logger.warning(f"Ignoring invalid signed genome from {sender_id}: {reason}")
                    return ""

                # Update local state after successful verification
                seen_nonces.add(envelope.nonce)
                self._last_seq[envelope.sender_node_id] = envelope.seq_no
                processed_payload = envelope.payload
            else:
                # Signature verification disabled, extract payload directly
                processed_payload = envelope.payload

            # --- Quarantine for memory.fact (applies whether signed or not, if enabled) ---
            if (self.quarantine and envelope.payload_type == self.MEMORY_FACT_PAYLOAD_TYPE
                    and config.quarantine_enabled):
                await self.quarantine.process(processed_payload)

        # --- Custom Data Types (e.g., heartbeat, meta_command) ---
        # 'processed_payload' holds the actual data after potential envelope unwrapping
        if isinstance(processed_payload, dict) and "type" in processed_payload:
            # Generate GID if not present
            gid: str = processed_payload.get("gid") or str(uuid.uuid4())
            # Add/update `node` and `ts` for consistency, if not already present
            if "node" not in processed_payload:
                processed_payload["node"] = self.node_id
            if "ts" not in processed_payload:
                processed_payload["ts"] = time.time()
            self.crdt.upsert(gid, processed_payload)
            logger.info(
                f"✅ Custom data imported: {gid[:8]}... (type={processed_payload.get('type')}) "
                f"from {sender_id}"
            )
            return gid

        # --- Standard Genome Processing ---
        # Generate GID if not present
        gid = processed_payload.get("gid") or str(uuid.uuid4())
        payload_to_upsert: Dict[str, Any] = {
            "params": processed_payload.get("params", {}),
            "fitness": float(processed_payload.get("fitness", 0.0)),
            "niche": processed_payload.get("niche", "exploration"),
            "origin": processed_payload.get("origin", self.node_id),  # Origin could be remote or local
            "lineage": processed_payload.get("lineage", [self.node_id]),
            "ts": processed_payload.get("ts", time.time()),
            "ver": int(processed_payload.get("ver", 0)),
            "node": processed_payload.get("node", self.node_id),  # Node that processed it, typically local
        }
        self.crdt.upsert(gid, payload_to_upsert)
        # Use 'sender_id' which is correctly set for gossip or defaults to 'local'
        logger.info(f"✅ Genome imported: {gid[:8]}... from {sender_id}")
        return gid

    async def merge(self, remote_items: Dict[str, Dict[str, Any]]) -> None:
        """
        Merges remote genome items into the local CRDT state.

        For each item, this method performs an 'upsert', creating a new CRDT operation
        with the current node's ID and timestamp. This method assumes `remote_items`
        are resolved genome states (not raw CRDT operations). If raw CRDT operations
        were being sent, `self.crdt.merge()` would be used directly.

        Args:
            remote_items (Dict[str, Dict[str, Any]]): A dictionary of genome items,
                                                      where keys are GIDs and values are genome payloads.
        """
        for gid, genome_payload in remote_items.items():
            self.crdt.upsert(gid, genome_payload)  # This creates a new op from THIS node_id

    async def get_nonce(self, account: str) -> int:
        """
        Retrieves the current nonce for a given account.
        Nonces are stored as special CRDT records.

        Args:
            account (str): The identifier of the account.

        Returns:
            int: The current nonce value, defaulting to 0 if not found or invalid.
        """
        gid: str = f"nonce:{account}"
        record_payload: Optional[Dict[str, Any]] = self.crdt.get(gid)
        if record_payload and isinstance(record_payload, dict):
            # The value could be int, but get() returns Any. Ensure it's an int.
            return int(record_payload.get("value", 0))
        return 0

    async def set_nonce(self, account: str, nonce: int) -> None:
        """
        Sets the nonce for a given account.

        Args:
            account (str): The identifier of the account.
            nonce (int): The new nonce value.
        """
        gid: str = f"nonce:{account}"
        data: Dict[str, Any] = {
            "key": gid,
            "value": nonce,
            "timestamp": time.time(),
            "node_id": self.node_id,
            "type": self.NONCE_RECORD_TYPE,
        }
        self.crdt.upsert(gid, data)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Computes the delta (new or updated genomes) compared to a known set of versions.
        This method returns full genome payloads, not raw CRDT operations.

        Note: `known_versions` here refers to the application-level `ver` field
        within the genome payload, not to internal CRDT Lamport clocks.

        Args:
            known_versions (Dict[str, int]): A dictionary mapping GID to an application-level
                                              version number, representing the caller's knowledge.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are GIDs and values are their
                                        full genome payloads that are newer than the provided
                                        `known_versions`.
        """
        all_state: Dict[str, Dict[str, Any]] = self.crdt.state()
        delta: Dict[str, Dict[str, Any]] = {}
        for gid, payload in all_state.items():
            # Compare application-level 'ver' field, defaulting to 0 if not present.
            app_ver: int = int(payload.get("ver", 0))
            if gid not in known_versions or known_versions[gid] < app_ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        """
        Retrieves the current application-level version ('ver' field) for all active genomes.

        Returns:
            Dict[str, int]: A dictionary mapping GID to its application-level version number.
        """
        all_state: Dict[str, Dict[str, Any]] = self.crdt.state()
        return {gid: int(payload.get("ver", 0)) for gid, payload in all_state.items()}

    async def get_top(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the top 'n' genomes based on their 'fitness' score.

        Args:
            n (int): The number of top genomes to retrieve. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a genome.
        """
        all_state: Dict[str, Dict[str, Any]] = self.crdt.state()
        # Sort based on 'fitness', defaulting to 0.0 if not present.
        # Explicitly cast to float for safe comparison.
        sorted_genomes: List[Dict[str, Any]] = sorted(
            all_state.values(),
            key=lambda x: float(x.get("fitness", 0.0)),
            reverse=True,
        )
        return sorted_genomes[:n]

    async def prune(self) -> None:
        """
        Performs pruning and compaction of the CRDT.

        Currently, this involves compacting the CRDT operation log.
        Future versions may implement logic for deleting old or irrelevant
        genomes from the CRDT state.
        """
        logger.debug("Running CRDT compaction...")
        self.crdt.compact()
        logger.debug("CRDT compaction finished.")

    async def prune_heartbeats(self, max_age_seconds: int = 600) -> None:
        """
        Deletes 'heartbeat' records from the CRDT that are older than `max_age_seconds`.

        Args:
            max_age_seconds (int): The maximum age in seconds for heartbeats
                                   before they are deleted. Defaults to 600 seconds (10 minutes).
        """
        now: float = time.time()
        to_delete: List[str] = []

        for gid, payload in self.crdt.state().items():
            if isinstance(payload, dict) and payload.get("type") == self.HEARTBEAT_RECORD_TYPE:
                # Ensure 'timestamp' is present and is a number for comparison.
                ts: float = float(payload.get("timestamp", 0.0))
                if now - ts > max_age_seconds:
                    to_delete.append(gid)

        for gid in to_delete:
            self.crdt.delete(gid)
        if to_delete:
            logger.info(f"Pruned {len(to_delete)} old heartbeats from CRDT.")

    @property
    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns the current active state of the CRDT, excluding deleted records (tombstones).
        Each genome payload is returned as a copy to prevent accidental modifications
        of the internal CRDT state.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are GIDs and values are
                                        the active genome payloads.
        """
        return self.crdt.state()