"""Signed gossip envelopes for authenticated swarm message exchange."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from binascii import Error as BinasciiError
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

ENVELOPE_VERSION: Literal["1.0"] = "1.0"
DOMAIN_BLACKSWAN_GOSSIP_V1: Literal["blackswan-gossip-v1"] = "blackswan-gossip-v1"

PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64
DEFAULT_TTL_MS = 60_000
MAX_CLOCK_SKEW_MS = 30_000


def canonical_dict(obj: Any) -> Any:
    """Recursively canonicalize JSON-compatible objects for deterministic signing."""
    if isinstance(obj, dict):
        return {str(key): canonical_dict(value) for key, value in sorted(obj.items(), key=lambda item: str(item[0]))}
    if isinstance(obj, list):
        return [canonical_dict(item) for item in obj]
    if isinstance(obj, tuple):
        return [canonical_dict(item) for item in obj]
    return obj


def canonical_json(obj: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes."""
    return json.dumps(
        canonical_dict(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    """Return SHA256 hex digest for bytes."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")

    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize().hex()


def now_ms() -> int:
    """Return current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def public_key_bytes(pubkey: Ed25519PublicKey) -> bytes:
    """Backward-compatible alias for raw public key bytes."""
    return public_key_bytes_raw(pubkey)


def public_key_bytes_raw(pubkey: Ed25519PublicKey) -> bytes:
    """Return raw 32-byte Ed25519 public key bytes."""
    if not isinstance(pubkey, Ed25519PublicKey):
        raise TypeError("pubkey must be Ed25519PublicKey")
    return pubkey.public_bytes_raw()


def public_key_id_from_raw_bytes(pubkey_raw_bytes: bytes) -> str:
    """Return SHA256 key id from raw public key bytes."""
    if not isinstance(pubkey_raw_bytes, bytes):
        raise TypeError("pubkey_raw_bytes must be bytes")
    if len(pubkey_raw_bytes) != PUBLIC_KEY_BYTES:
        raise ValueError(f"public key must be {PUBLIC_KEY_BYTES} bytes")
    return sha256(pubkey_raw_bytes)


def b64encode(data: bytes) -> str:
    """Base64 encode bytes to ASCII string."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    return base64.b64encode(data).decode("ascii")


def b64decode(data: str) -> bytes:
    """Base64 decode ASCII string to bytes."""
    return base64.b64decode(str(data or ""), validate=True)


def generate_key_pair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a new Ed25519 key pair."""
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def public_key_from_b64(public_key_b64: str) -> Ed25519PublicKey:
    """Decode a raw Ed25519 public key from base64."""
    raw = b64decode(public_key_b64)
    if len(raw) != PUBLIC_KEY_BYTES:
        raise ValueError(f"public key must be {PUBLIC_KEY_BYTES} bytes")
    return Ed25519PublicKey.from_public_bytes(raw)


class GossipEnvelope(BaseModel):
    """Signed gossip message envelope."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    envelope_version: Literal["1.0"] = ENVELOPE_VERSION
    domain: Literal["blackswan-gossip-v1"] = DOMAIN_BLACKSWAN_GOSSIP_V1
    payload_type: str
    topic: str

    sender_peer_id: str
    sender_node_id: str
    sender_pubkey: str
    key_id: str
    key_version: int = Field(ge=1)

    seq_no: int = Field(ge=0)
    lamport_ts: int = Field(ge=0)
    nonce: str
    timestamp_ms: int = Field(ge=0)

    ttl_ms: int = Field(default=DEFAULT_TTL_MS, ge=0)
    expires_at_ms: int = Field(ge=0)

    parent_hashes: list[str] = Field(default_factory=list)
    payload_hash: str
    payload: Any
    signature: str = ""

    trace_id: str | None = None
    correlation_id: str | None = None

    @field_validator(
        "payload_type",
        "topic",
        "sender_peer_id",
        "sender_node_id",
        "sender_pubkey",
        "key_id",
        "nonce",
        "payload_hash",
        mode="before",
    )
    @classmethod
    def _clean_required_text(cls, value: Any) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("value cannot be empty")
        return clean

    @field_validator("parent_hashes", mode="before")
    @classmethod
    def _normalize_parent_hashes(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("parent_hashes must be a list")
        return [str(item).strip() for item in value if str(item or "").strip()]

    @model_validator(mode="after")
    def _validate_hashes_and_expiry(self) -> GossipEnvelope:
        if self.expires_at_ms < self.timestamp_ms:
            raise ValueError("expires_at_ms cannot be earlier than timestamp_ms")

        if self.ttl_ms and self.expires_at_ms != self.timestamp_ms + self.ttl_ms:
            # Keep compatibility with explicit expires_at_ms, but normalize impossible drift only when missing is not possible.
            if self.expires_at_ms <= self.timestamp_ms:
                self.expires_at_ms = self.timestamp_ms + self.ttl_ms

        expected_payload_hash = sha256(canonical_json(self.payload))
        if self.payload_hash != expected_payload_hash:
            raise ValueError("payload_hash does not match payload")

        return self

    @property
    def signing_preimage(self) -> bytes:
        """Return canonical signing preimage excluding signature."""
        return canonical_json(self.model_dump(exclude={"signature"}, mode="json"))

    @property
    def expired(self) -> bool:
        """Return True if envelope is expired at current time."""
        return now_ms() > self.expires_at_ms

    def sender_public_key(self) -> Ed25519PublicKey:
        """Return public key decoded from sender_pubkey."""
        return public_key_from_b64(self.sender_pubkey)


def sign_envelope(
    payload: Any,
    meta: dict[str, Any],
    private_key: Ed25519PrivateKey,
) -> GossipEnvelope:
    """Create and sign a GossipEnvelope."""
    if not isinstance(meta, dict):
        raise TypeError("meta must be a dictionary")
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("private_key must be Ed25519PrivateKey")

    public_key = private_key.public_key()
    public_raw = public_key_bytes_raw(public_key)
    sender_pubkey = b64encode(public_raw)
    key_id = public_key_id_from_raw_bytes(public_raw)

    timestamp = int(meta.get("timestamp_ms") or now_ms())
    ttl_ms_value = int(meta.get("ttl_ms") or DEFAULT_TTL_MS)

    envelope_data = dict(meta)
    envelope_data["sender_pubkey"] = sender_pubkey
    envelope_data["key_id"] = key_id
    envelope_data["timestamp_ms"] = timestamp
    envelope_data["ttl_ms"] = ttl_ms_value
    envelope_data["expires_at_ms"] = int(meta.get("expires_at_ms") or (timestamp + ttl_ms_value))
    envelope_data["payload"] = payload
    envelope_data["payload_hash"] = sha256(canonical_json(payload))
    envelope_data["signature"] = ""

    try:
        envelope = GossipEnvelope.model_validate(envelope_data)
    except ValidationError:
        logger.exception("Failed to create GossipEnvelope from metadata.")
        raise

    signature = private_key.sign(envelope.signing_preimage)
    envelope.signature = b64encode(signature)
    return envelope


def verify_envelope(
    envelope: GossipEnvelope | dict[str, Any],
    public_key: Ed25519PublicKey,
    seen_nonces: set[str],
    last_seq: int,
    now_ms: int,
) -> tuple[bool, str]:
    """Verify envelope freshness, replay protection, ordering, identity, hash, and signature."""
    try:
        env = envelope if isinstance(envelope, GossipEnvelope) else GossipEnvelope.model_validate(envelope)
    except ValidationError as exc:
        return False, f"invalid envelope: {exc}"

    if not isinstance(public_key, Ed25519PublicKey):
        return False, "public_key must be Ed25519PublicKey"

    if not isinstance(seen_nonces, set):
        return False, "seen_nonces must be a set"

    current_ms = int(now_ms)

    if env.expires_at_ms < current_ms:
        return False, "expired"

    if env.timestamp_ms > current_ms + MAX_CLOCK_SKEW_MS:
        return False, "timestamp from future"

    if env.nonce in seen_nonces:
        return False, "replay"

    if env.seq_no <= int(last_seq):
        return False, f"non-monotonic seq_no: envelope seq_no {env.seq_no} is not greater than last seen {last_seq}"

    actual_payload_hash = sha256(canonical_json(env.payload))
    if actual_payload_hash != env.payload_hash:
        return False, f"payload hash mismatch: expected {env.payload_hash}, got {actual_payload_hash}"

    expected_public_raw = public_key_bytes_raw(public_key)
    expected_sender_pubkey = b64encode(expected_public_raw)
    expected_key_id = public_key_id_from_raw_bytes(expected_public_raw)

    if env.sender_pubkey != expected_sender_pubkey:
        return False, (
            "sender_pubkey in envelope does not match provided public_key. "
            f"Expected: {expected_sender_pubkey[:16]}..., Got: {env.sender_pubkey[:16]}..."
        )

    if env.key_id != expected_key_id:
        return False, (
            "key_id in envelope does not match provided public_key. "
            f"Expected: {expected_key_id[:8]}..., Got: {env.key_id[:8]}..."
        )

    try:
        signature = b64decode(env.signature)
        if len(signature) != SIGNATURE_BYTES:
            return False, f"signature must be {SIGNATURE_BYTES} bytes"

        public_key.verify(signature, env.signing_preimage)
    except (InvalidSignature, BinasciiError, ValueError) as exc:
        return False, f"bad signature or malformed base64 signature string: {exc}"
    except Exception as exc:
        logger.exception("Unexpected error during envelope signature verification.")
        return False, f"unexpected error during signature verification: {type(exc).__name__}: {exc}"

    return True, ""


def verify_envelope_self_signed(
    envelope: GossipEnvelope | dict[str, Any],
    seen_nonces: set[str] | None = None,
    last_seq: int = -1,
    now_ms_value: int | None = None,
) -> tuple[bool, str]:
    """Verify envelope using sender_pubkey embedded in the envelope.

    Use this only when sender identity is already accepted by a higher-level trust layer.
    """
    try:
        env = envelope if isinstance(envelope, GossipEnvelope) else GossipEnvelope.model_validate(envelope)
        public_key = env.sender_public_key()
    except Exception as exc:
        return False, f"invalid sender public key: {exc}"

    return verify_envelope(
        env,
        public_key,
        seen_nonces if seen_nonces is not None else set(),
        last_seq,
        now_ms_value if now_ms_value is not None else now_ms(),
    )


def make_meta(
    *,
    payload_type: str,
    topic: str,
    sender_peer_id: str,
    sender_node_id: str,
    seq_no: int,
    lamport_ts: int,
    key_version: int = 1,
    ttl_ms: int = DEFAULT_TTL_MS,
    parent_hashes: list[str] | None = None,
    trace_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build common envelope metadata."""
    timestamp = now_ms()
    return {
        "envelope_version": ENVELOPE_VERSION,
        "domain": DOMAIN_BLACKSWAN_GOSSIP_V1,
        "payload_type": payload_type,
        "topic": topic,
        "sender_peer_id": sender_peer_id,
        "sender_node_id": sender_node_id,
        "sender_pubkey": "",
        "key_id": "",
        "key_version": key_version,
        "seq_no": seq_no,
        "lamport_ts": lamport_ts,
        "nonce": os.urandom(16).hex(),
        "timestamp_ms": timestamp,
        "ttl_ms": ttl_ms,
        "expires_at_ms": timestamp + ttl_ms,
        "parent_hashes": parent_hashes or [],
        "trace_id": trace_id,
        "correlation_id": correlation_id,
    }