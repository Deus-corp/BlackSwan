# src/core/secure_gossip_adapter.py
import json
import time
import logging
from typing import Any, Dict, Optional, Set
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from src.security.gossip_envelope import (
    GossipEnvelope, generate_key_pair, public_key_bytes,
    sign_envelope, verify_envelope, sha256, canonical_json
)
from src.core.gossip_adapter import SafeGossipAdapter

logger = logging.getLogger(__name__)

class SecureGossipAdapter:
    def __init__(self, crdt_adapter, node_id: str, private_key: Ed25519PrivateKey, enable_signing: bool = True):
        self.inner = SafeGossipAdapter(crdt_adapter)
        self.node_id = node_id
        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.pubkey_bytes = public_key_bytes(self.public_key)
        self.key_id = sha256(self.pubkey_bytes)
        self.enable_signing = enable_signing
        self._seen_nonces: Dict[str, Set[str]] = {}
        self._last_seq_no: Dict[str, int] = {}
        self._key_version = 1
        self._lamport_clock = 0

    def _next_seq_no(self, sender_node_id: str) -> int:
        """Возвращает следующий seq_no для указанного узла (обычно это мы сами)."""
        self._last_seq_no.setdefault(sender_node_id, -1)
        self._last_seq_no[sender_node_id] += 1
        return self._last_seq_no[sender_node_id]

    def _next_nonce(self) -> str:
        import os
        return os.urandom(16).hex()

    async def send_message(self, peer: str, payload: Any, payload_type: str = "memory.fact", topic: str = "swarm") -> bool:
        """Отправляет подписанное сообщение (или без подписи, если enable_signing=False)."""
        if not self.enable_signing:
            # Проксируем вызов к внутреннему адаптеру без изменений
            return await self.inner.send_message(peer, payload)

        meta = {
            "envelope_version": "1.0",
            "domain": "blackswan-gossip-v1",
            "payload_type": payload_type,
            "topic": topic,
            "sender_peer_id": peer,  # временно, нужно подставить свой peer id
            "sender_node_id": self.node_id,
            "sender_pubkey": self.pubkey_bytes,
            "key_id": self.key_id,
            "key_version": self._key_version,
            "seq_no": self._next_seq_no(self.node_id),
            "lamport_ts": self._lamport_clock,
            "nonce": self._next_nonce(),
            "timestamp_ms": int(time.time() * 1000),
            "ttl_ms": 30000,
            "expires_at_ms": int(time.time() * 1000) + 30000,
            "parent_hashes": [],
        }

        envelope = sign_envelope(payload, meta, self.private_key, public_key_bytes=self.pubkey_bytes)
        envelope_dict = envelope.model_dump(mode='json')
        # Отправляем JSON-представление конверта
        return await self.inner.send_message(peer, envelope_dict)

    async def handle_incoming(self, data: Any) -> Optional[Any]:
        """Обрабатывает входящие данные. Если подпись включена, ожидает конверт и проверяет его.
        Возвращает payload валидного сообщения или None, если сообщение не прошло проверку.
        """
        if not self.enable_signing:
            return data  # возвращаем как есть

        try:
            # Пробуем интерпретировать как GossipEnvelope
            envelope = GossipEnvelope(**data)
        except Exception:
            logger.warning("Received non-envelope message while signing is enabled, discarding")
            return None

        now_ms = int(time.time() * 1000)
        # Получаем публичный ключ отправителя из конверта (мы доверяем ему, т.к. проверяем подпись)
        sender_pubkey = envelope.sender_pubkey
        try:
            pubkey = Ed25519PublicKey.from_public_bytes(sender_pubkey)
        except Exception:
            logger.warning("Invalid public key in envelope")
            return None

        # Набор уже виденных nonce для этого отправителя
        sender_node = envelope.sender_node_id
        seen = self._seen_nonces.setdefault(sender_node, set())
        last_seq = self._last_seq_no.get(sender_node, -1)

        valid, reason = verify_envelope(envelope, pubkey, seen, last_seq, now_ms)
        if not valid:
            logger.warning(f"Envelope verification failed: {reason}")
            return None

        # Обновляем состояние защиты
        seen.add(envelope.nonce)
        self._last_seq_no[sender_node] = envelope.seq_no
        self._lamport_clock = max(self._lamport_clock, envelope.lamport_ts) + 1

        return envelope.payload

    # Проксируем остальные методы
    async def start(self) -> None:
        await self.inner.start()

    async def shutdown(self) -> None:
        await self.inner.shutdown()