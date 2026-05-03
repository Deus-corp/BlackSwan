"""
Адаптер, который заменяет CRDTState на GenomeCRDT с SQLite‑персистентностью.
Совместим с текущим node_agent.py.
"""
import uuid
import os
import time
import asyncio
import logging
from typing import Any, Dict, Optional
from src.core.crdt_layer import GenomeCRDT, CRDTStorage
from src.security.gossip_envelope import GossipEnvelope, verify_envelope
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.core.gossip_filter import GossipFilter

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("CRDT_DB_PATH", "./crdt_state.db")

class CRDTAdapter:
    def __init__(self, node_id: str, memory_api=None, reputation=None):
        self.node_id = node_id
        storage = CRDTStorage(DB_PATH)
        self.crdt = GenomeCRDT(node_id, storage=storage)
        self._seen_nonces: dict[str, set] = {}
        self._last_seq: dict[str, int] = {}
        self.memory_api = memory_api
        self.reputation = reputation
        self.gossip_filter = GossipFilter(max_clock_skew_ms=10_000)
        if memory_api and reputation:
            from src.memory.quarantine import QuarantineBuffer
            self.quarantine = QuarantineBuffer(memory_api, reputation)
        else:
            self.quarantine = None

    async def add_genome(self, genome: Dict[str, Any]) -> str:
        """Добавляет геном и возвращает gid."""

        # --- ПРОВЕРКА НА GOSSIP ENVELOPE ---
        if isinstance(genome, dict) and genome.get("domain") == "blackswan-gossip-v1":
            if os.environ.get("GOSSIP_SIGNING_ENABLED", "false").lower() == "true":
                try:
                    envelope = GossipEnvelope(**genome)
                except Exception:
                    logger.warning("Invalid envelope format, discarding")
                    return ""

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
               
                sender_pubkey_bytes = envelope.sender_pubkey
                try:
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
                # Извлекаем payload
                genome = envelope.payload

                # --- КАРАНТИН ДЛЯ memory.fact ---
                if self.quarantine and envelope.payload_type == "memory.fact":
                    await self.quarantine.process(genome)

            else:
                try:
                    envelope = GossipEnvelope(**genome)
                except Exception:
                    logger.warning("Invalid envelope format (signing disabled), discarding")
                    return ""

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

                genome = envelope.payload

                # --- КАРАНТИН ДЛЯ memory.fact ---
                if self.quarantine and envelope.payload_type == "memory.fact":
                    await self.quarantine.process(genome)

        # --- Обычная обработка genome (теперь genome – это исходные данные) ---
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
        return gid

    async def merge(self, remote_items: Dict[str, Dict[str, Any]]) -> None:
        for gid, genome in remote_items.items():
            self.crdt.upsert(gid, genome)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        all_state = self.crdt.state()
        delta = {}
        for gid, payload in all_state.items():
            ver = payload.get("ver", 0)
            if gid not in known_versions or known_versions[gid] < ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        all_state = self.crdt.state()
        return {gid: payload.get("ver", 0) for gid, payload in all_state.items()}

    async def get_top(self, n: int = 5):
        all_state = self.crdt.state()
        sorted_genomes = sorted(all_state.values(), key=lambda x: x.get("fitness", 0.0), reverse=True)
        return sorted_genomes[:n]

    async def prune(self) -> None:
        pass

    @property
    def state(self):
        return self.crdt.state()