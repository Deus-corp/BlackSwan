"""
Адаптер, который заменяет CRDTState на GenomeCRDT с SQLite‑персистентностью.
Совместим с текущим node_agent.py.
"""
import uuid
import os
import time
import asyncio
import logging
from typing import Any, Dict, Optional, Set, List
from src.core.crdt_layer import GenomeCRDT, CRDTStorage
from src.security.gossip_envelope import GossipEnvelope, verify_envelope, b64decode
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.core.gossip_filter import GossipFilter
from swarm_config import config   # добавляем для единообразного доступа к настройкам

logger = logging.getLogger(__name__)

# Removed duplicate import: from swarm_config import config
DB_PATH = config.crdt_db_path

class CRDTAdapter:
    """
    An adapter that integrates GenomeCRDT with SQLite persistence.
    Compatible with the existing node_agent.py.
    """
    _seen_nonces: Dict[str, Set[str]]
    _last_seq: Dict[str, int]
    quarantine: Optional["QuarantineBuffer"] # Forward reference for QuarantineBuffer

    def __init__(self, node_id: str, memory_api: Optional[Any] = None, reputation: Optional[Any] = None, db_path: Optional[str] = None) -> None:
        """
        Initializes the CRDTAdapter.

        Args:
            node_id (str): The ID of the current node.
            memory_api (Optional[Any]): The memory API object, if available.
            reputation (Optional[Any]): The reputation object, if available.
            db_path (Optional[str]): The path to the SQLite database file.
                                      If None, uses `config.crdt_db_path`.
        """
        self.node_id = node_id
        # Если db_path не передан, используем значение из конфига
        path = db_path or config.crdt_db_path
        storage = CRDTStorage(path)
        self.crdt = GenomeCRDT(node_id, storage=storage)
        self.storage = storage
        self._seen_nonces = {}
        self._last_seq = {}
        self.memory_api = memory_api
        self.reputation = reputation
        self.gossip_filter = GossipFilter(max_clock_skew_ms=10_000)
        if memory_api and reputation:
            from src.memory.quarantine import QuarantineBuffer
            self.quarantine = QuarantineBuffer(memory_api, reputation)
        else:
            self.quarantine = None

    async def add_genome(self, genome: Dict[str, Any]) -> str:
        """
        Добавляет геном и возвращает gid.
        Handles gossip envelopes, custom data types, and standard genome payloads.

        Args:
            genome (Dict[str, Any]): The genome or gossip envelope to add.

        Returns:
            str: The globally unique ID (gid) of the added genome, or an empty string
                 if the genome was invalid or rejected.
        """
        # Store original genome for later checks if it wasn't a gossip envelope
        original_genome = genome
        sender_id = "local" # Default sender for logging

        # --- ПРОВЕРКА НА GOSSIP ENVELOPE ---
        if isinstance(genome, dict) and genome.get("domain") == "blackswan-gossip-v1":
            # Используем единый источник конфигурации
            try:
                envelope = GossipEnvelope(**genome)
            except Exception:
                logger.warning("Invalid envelope format, discarding")
                return ""

            sender_id = envelope.sender_node_id # Update sender_id for logging

            # --- GOSSIP FILTER ---
            if not self.gossip_filter.check(
                sender_node_id=envelope.sender_node_id,
                nonce=envelope.nonce,
                seq_no=envelope.seq_no,
                timestamp_ms=envelope.timestamp_ms,
                ttl_ms=envelope.ttl_ms
            ):
                logger.warning("Gossip message rejected by filter")
                return ""

            if config.gossip_signing_enabled:
                # Декодируем публичный ключ из base64
                try:
                    sender_pubkey_bytes = b64decode(envelope.sender_pubkey)
                    pubkey = Ed25519PublicKey.from_public_bytes(sender_pubkey_bytes)
                except Exception:
                    logger.warning("Invalid public key in envelope, discarding")
                    return ""

                now_ms = int(time.time() * 1000)
                seen_nonces = self._seen_nonces.setdefault(envelope.sender_node_id, set())
                last_seq = self._last_seq.get(envelope.sender_node_id, -1)
                valid, reason = verify_envelope(envelope, pubkey, seen_nonces, last_seq, now_ms)
                if not valid:
                    logger.warning(f"Ignoring invalid signed genome: {reason}")
                    return ""
                seen_nonces.add(envelope.nonce)
                self._last_seq[envelope.sender_node_id] = envelope.seq_no

                genome = envelope.payload

                # --- КАРАНТИН ДЛЯ memory.fact ---
                if self.quarantine and envelope.payload_type == "memory.fact" and config.quarantine_enabled:
                    await self.quarantine.process(genome)

            else:
                # Проверка подписи отключена, но фильтр всё равно применяем
                # Envelope already parsed above
                genome = envelope.payload

                # --- КАРАНТИН ДЛЯ memory.fact ---
                # Added config.quarantine_enabled check for consistency with the signed path
                if self.quarantine and envelope.payload_type == "memory.fact" and config.quarantine_enabled:
                    await self.quarantine.process(genome)

        # --- Пользовательские типы данных (heartbeat, meta_command и т.д.) ---
        # Note: 'genome' might have been updated to 'envelope.payload' at this point
        if isinstance(genome, dict) and "type" in genome:
            gid = genome.get("gid") or str(uuid.uuid4())
            # Сохраняем как есть, не преобразуем в стандартный genome
            self.crdt.upsert(gid, genome)
            logger.info(f"✅ Custom data imported: {gid[:8]}... (type={genome.get('type')})")
            return gid

        # --- Обычная обработка genome ---
        gid = genome.get("gid") or str(uuid.uuid4())
        payload = {
            "params": genome.get("params", {}),
            "fitness": genome.get("fitness", 0.0),
            "niche": genome.get("niche", "exploration"),
            "origin": genome.get("origin", self.node_id),
            "lineage": genome.get("lineage", [self.node_id]),
            "ts": genome.get("ts", time.time()),
            "ver": genome.get("ver", 0),
            "node": genome.get("node", self.node_id),
        }
        self.crdt.upsert(gid, payload)
        # Fixed: Use 'sender_id' which is correctly set for gossip or defaults to 'local'
        logger.info(f"✅ Genome imported: {gid[:8]}... from {sender_id}")
        return gid

    async def merge(self, remote_items: Dict[str, Dict[str, Any]]) -> None:
        """
        Merges remote genome items into the local CRDT state.

        Args:
            remote_items (Dict[str, Dict[str, Any]]): A dictionary of genome items
                                                      where keys are GIDs and values are genome payloads.
        """
        for gid, genome in remote_items.items():
            self.crdt.upsert(gid, genome)

    async def get_nonce(self, account: str) -> int:
        """
        Retrieves the current nonce for a given account.

        Args:
            account (str): The account identifier.

        Returns:
            int: The current nonce, defaults to 0 if not found.
        """
        gid = f"nonce:{account}"
        state = self.crdt.state()
        record = state.get(gid)
        if record and isinstance(record, dict):
            return record.get("value", 0)
        return 0

    async def set_nonce(self, account: str, nonce: int) -> None:
        """
        Sets the nonce for a given account.

        Args:
            account (str): The account identifier.
            nonce (int): The new nonce value.
        """
        gid = f"nonce:{account}"
        data = {
            "key": gid,
            "value": nonce,
            "timestamp": time.time(),
            "node_id": self.node_id,
        }
        self.crdt.upsert(gid, data)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Calculates the delta (new or updated genomes) since a given set of known versions.

        Args:
            known_versions (Dict[str, int]): A dictionary of GID to version number
                                              representing the caller's knowledge.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary of GIDs and their full genome payloads
                                        that are newer than the provided known_versions.
        """
        all_state = self.crdt.state()
        delta = {}
        for gid, payload in all_state.items():
            ver = payload.get("ver", 0)
            if gid not in known_versions or known_versions[gid] < ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        """
        Retrieves the current version (ver field) for all active genomes.

        Returns:
            Dict[str, int]: A dictionary of GID to version number.
        """
        all_state = self.crdt.state()
        return {gid: payload.get("ver", 0) for gid, payload in all_state.items()}

    async def get_top(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the top 'n' genomes based on their 'fitness' score.

        Args:
            n (int): The number of top genomes to retrieve. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a genome.
        """
        all_state = self.crdt.state()
        sorted_genomes = sorted(all_state.values(), key=lambda x: x.get("fitness", 0.0), reverse=True)
        return sorted_genomes[:n]

    async def prune(self) -> None:
        """
        Placeholder for pruning logic. Currently does nothing.
        """
        pass

    async def prune_heartbeats(self, max_age_seconds: int = 600) -> None:
        """
        Удаляет heartbeats старше max_age_seconds.

        Args:
            max_age_seconds (int): The maximum age in seconds for heartbeats
                                   before they are pruned. Defaults to 600 seconds (10 minutes).
        """
        now = time.time()
        to_delete = []
        for k, v in self.crdt.state().items():
            if isinstance(v, dict) and v.get("type") == "heartbeat":
                ts = v.get("timestamp", 0)
                if now - ts > max_age_seconds:
                    to_delete.append(k)
        for k in to_delete:
            self.crdt.delete(k)
        if to_delete:
            logger.info(f"Pruned {len(to_delete)} old heartbeats from CRDT")

    @property
    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns the current state of the CRDT, excluding deleted records.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are GIDs and values are
                                        the active genome payloads.
        """
        return self.crdt.state()