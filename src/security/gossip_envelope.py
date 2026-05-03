# src/security/gossip_envelope.py
import json
import time
import os
from typing import Optional, Any, List, Literal
from pydantic import BaseModel, Field
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
import base64

# ---------- Вспомогательные функции ----------

def canonical_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: canonical_dict(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [canonical_dict(item) for item in obj]
    else:
        return obj

def canonical_json(obj: Any) -> bytes:
    return json.dumps(canonical_dict(obj), sort_keys=True, separators=(',', ':')).encode('utf-8')

def sha256(data: bytes) -> str:
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize().hex()

# ---------- Кодирование ключей ----------

def public_key_bytes(pubkey: Ed25519PublicKey) -> bytes:
    return pubkey.public_bytes_raw()

def public_key_id(pubkey: bytes) -> str:
    return sha256(pubkey)

def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')

def b64decode(data: str) -> bytes:
    return base64.b64decode(data)

# ---------- Модель конверта ----------

class GossipEnvelope(BaseModel):
    envelope_version: Literal["1.0"] = "1.0"
    domain: Literal["blackswan-gossip-v1"] = "blackswan-gossip-v1"
    payload_type: str
    topic: str

    sender_peer_id: str
    sender_node_id: str
    sender_pubkey: str              # base64
    key_id: str                     # hex
    key_version: int

    seq_no: int
    lamport_ts: int
    nonce: str
    timestamp_ms: int

    ttl_ms: int
    expires_at_ms: int

    parent_hashes: List[str] = Field(default_factory=list)
    payload_hash: str
    payload: Any
    signature: str = ""             # base64

    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None

# ---------- Ключи ----------

def generate_key_pair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key

# ---------- Подпись и проверка ----------

def sign_envelope(
    payload: Any,
    meta: dict,
    private_key: Ed25519PrivateKey
) -> GossipEnvelope:
    """
    Создаёт подписанный GossipEnvelope.
    meta должен содержать все поля, кроме payload, payload_hash, signature.
    sender_pubkey может быть bytes или base64-строкой.
    """
    # Обработка sender_pubkey: приводим к base64
    if isinstance(meta.get('sender_pubkey'), bytes):
        meta = meta.copy()
        meta['sender_pubkey'] = b64encode(meta['sender_pubkey'])

    # Вычисляем хеш payload
    payload_b = canonical_json(payload)
    payload_hash = sha256(payload_b)

    # Создаём конверт без подписи
    envelope_data = meta.copy()
    envelope_data['payload'] = payload
    envelope_data['payload_hash'] = payload_hash
    envelope_data['signature'] = ""

    env = GossipEnvelope(**envelope_data)

    # Подписываем пре-image (все поля кроме signature)
    env_dict = env.model_dump(exclude={'signature'})
    preimage = canonical_json(env_dict)
    sig_bytes = private_key.sign(preimage)
    env.signature = b64encode(sig_bytes)
    return env

def verify_envelope(envelope: GossipEnvelope, public_key: Ed25519PublicKey, seen_nonces: set, last_seq: int, now_ms: int) -> tuple[bool, str]:
    """Проверяет конверт. Возвращает (True, "") или (False, причина)."""
    if now_ms > envelope.expires_at_ms:
        return False, "expired"

    if envelope.nonce in seen_nonces:
        return False, "replay"

    if envelope.seq_no <= last_seq:
        return False, "non-monotonic seq_no"

    actual_hash = sha256(canonical_json(envelope.payload))
    if actual_hash != envelope.payload_hash:
        return False, "payload hash mismatch"

    # Подпись
    env_dict = envelope.model_dump(exclude={'signature'})
    preimage = canonical_json(env_dict)
    try:
        signature_bytes = b64decode(envelope.signature)
        public_key.verify(signature_bytes, preimage)
    except (InvalidSignature, Exception):
        return False, "bad signature"

    return True, ""