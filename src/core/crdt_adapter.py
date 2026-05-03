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

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("CRDT_DB_PATH", "./crdt_state.db")

class CRDTAdapter:
    def __init__(self, node_id: str):
        self.node_id = node_id
        storage = CRDTStorage(DB_PATH)
        self.crdt = GenomeCRDT(node_id, storage=storage)
        self._seen_nonces: dict[str, set] = {}
        self._last_seq: dict[str, int] = {}

    async def add_genome(self, genome: Dict[str, Any]) -> str:
        """Добавляет геном и возвращает gid."""

        # --- ПРОВЕРКА НА GOSSIP ENVELOPE ---
        if isinstance(genome, dict) and genome.get("domain") == "blackswan-gossip-v1":
            # Это подписанный конверт
            if os.environ.get("GOSSIP_SIGNING_ENABLED", "false").lower() == "true":
                try:
                    envelope = GossipEnvelope(**genome)
                except Exception:
                    logger.warning("Invalid envelope format, discarding")
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
                # Извлекаем payload – именно он и есть исходный genome
                genome = envelope.payload
            else:
                # Подпись не требуется, просто извлекаем payload
                try:
                    envelope = GossipEnvelope(**genome)
                    genome = envelope.payload
                except Exception:
                    logger.warning("Invalid envelope format (signing disabled), discarding")
                    return ""

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
        """Принимает словарь {gid: genome_dict} от других узлов."""
        for gid, genome in remote_items.items():
            # При merge тоже могут приходить envelope? Сейчас предполагаем, что нет.
            # При необходимости можно добавить такую же проверку, как в add_genome.
            self.crdt.upsert(gid, genome)

    async def get_delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает словарь геномов, которые новее, чем known_versions.
        Для совместимости с текущим gossip.
        """
        all_state = self.crdt.state()
        delta = {}
        for gid, payload in all_state.items():
            ver = payload.get("ver", 0)
            if gid not in known_versions or known_versions[gid] < ver:
                delta[gid] = payload
        return delta

    async def get_versions(self) -> Dict[str, int]:
        """Возвращает {gid: ver} для всех геномов."""
        all_state = self.crdt.state()
        return {gid: payload.get("ver", 0) for gid, payload in all_state.items()}

    async def get_top(self, n: int = 5):
        """Возвращает топ-N геномов по фитнесу."""
        all_state = self.crdt.state()
        sorted_genomes = sorted(all_state.values(), key=lambda x: x.get("fitness", 0.0), reverse=True)
        return sorted_genomes[:n]

    async def prune(self) -> None:
        """Удаляет старые записи (реализовано на уровне CRDTStorage по TTL)."""
        pass

    @property
    def state(self):
        """Для обратной совместимости с crdt_size в логах."""
        return self.crdt.state()