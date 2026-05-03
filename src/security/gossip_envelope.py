# src/security/gossip_envelope.py
import json
import time
from typing import Optional, Any, List
from pydantic import BaseModel, Field
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
import os

# ---------- Вспомогательные функции ----------

def canonical_dict(obj: Any) -> Any:
    """Приводит объект к каноническому виду: сортирует ключи в словарях, списки оставляет как есть."""
    if isinstance(obj, dict):
        return {k: canonical_dict(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [canonical_dict(item) for item in obj]
    else:
        return obj

def canonical_json(obj: Any) -> bytes:
    """Сериализует объект в канонический JSON (отсортированные ключи, без лишних пробелов)."""
    return json.dumps(canonical_dict(obj), sort_keys=True, separators=(',', ':')).encode('utf-8')

def sha256(data: bytes) -> str:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize().hex()

# ---------- Модели данных ----------

class GossipEnvelope(BaseModel):
    envelope_version: str = Field("1.0", const=True)
    domain: str = Field("blackswan-gossip-v1", const=True)
    payload_type: str  # "memory.fact", "decision.proposal" и т.д.
    topic: str

    sender_peer_id: str
    sender_node_id: str
    sender_pubkey: bytes  # Ed25519 public key bytes (raw)
    key_id: str  # хеш публичного ключа
    key_version: int

    seq_no: int
    lamport_ts: int
    nonce: str
    timestamp_ms: int

    ttl_ms: int
    expires_at_ms: int

    parent_hashes: List[str] = Field(default_factory=list)
    payload_hash: str
    payload: Any  # фактически GossipPayload
    signature: bytes = b""

    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None

# ---------- Ключи ----------

def generate_key_pair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key

def public_key_bytes(pubkey: Ed25519PublicKey) -> bytes:
    return pubkey.public_bytes(Encoding.Raw, PublicFormat.Raw)

def public_key_id(pubkey: bytes) -> str:
    return sha256(pubkey)

# ---------- Подпись и проверка ----------

def sign_envelope(
    payload: Any,
    meta: dict,
    private_key: Ed25519PrivateKey,
    public_key_bytes_hex: str = None  # для удобства
) -> GossipEnvelope:
    """
    Создаёт подписанный GossipEnvelope.
    meta должен содержать все поля, кроме payload, payload_hash, signature.
    """
    # Вычисляем хеш payload
    payload_b = canonical_json(payload)
    payload_hash = sha256(payload_b)

    # Создаём конверт без подписи
    envelope_data = meta.copy()
    envelope_data['payload'] = payload
    envelope_data['payload_hash'] = payload_hash
    envelope_data['signature'] = b""
    # Остальные поля уже должны быть в meta (envelope_version, domain, sender_*, seq_no, nonce, ...)

    # Строим объект (валидация pydantic)
    env = GossipEnvelope(**envelope_data)

    # Подписываем пре-image (все поля кроме signature)
    # Используем канонический JSON объекта envelope без поля signature
    env_dict = env.model_dump(exclude={'signature'})
    preimage = canonical_json(env_dict)
    sig = private_key.sign(preimage)
    env.signature = sig
    return env

def verify_envelope(envelope: GossipEnvelope, public_key: Ed25519PublicKey, seen_nonces: set, last_seq: int, now_ms: int) -> tuple[bool, str]:
    """Проверяет конверт. Возвращает (True, "") или (False, причина)."""
    # Проверка срока действия
    if now_ms > envelope.expires_at_ms:
        return False, "expired"

    # Проверка nonce (повтор)
    if envelope.nonce in seen_nonces:
        return False, "replay"

    # Проверка seq_no монотонность
    if envelope.seq_no <= last_seq:
        return False, "non-monotonic seq_no"

    # Проверим хеш payload
    actual_hash = sha256(canonical_json(envelope.payload))
    if actual_hash != envelope.payload_hash:
        return False, "payload hash mismatch"

    # Проверка подписи
    env_dict = envelope.model_dump(exclude={'signature'})
    preimage = canonical_json(env_dict)
    try:
        public_key.verify(envelope.signature, preimage)
    except InvalidSignature:
        return False, "bad signature"

    return True, ""