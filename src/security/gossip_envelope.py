import json
import time
import os
import base64
from typing import Optional, Any, List, Literal, Dict
from pydantic import BaseModel, Field, ValidationError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
from binascii import Error as BinasciiError # For base64 decoding errors

# ---------- Constants ----------
ENVELOPE_VERSION = "1.0"
DOMAIN_BLACKSWAN_GOSSIP_V1 = "blackswan-gossip-v1"

# ---------- Utility Functions ----------

def canonical_dict(obj: Any) -> Any:
    """
    Recursively sorts dictionaries by key and processes lists for consistent serialization.
    This ensures a deterministic representation of the object, which is crucial for
    hashing and signing operations.
    """
    if isinstance(obj, dict):
        return {k: canonical_dict(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [canonical_dict(item) for item in obj]
    else:
        return obj

def canonical_json(obj: Any) -> bytes:
    """
    Converts an object to its canonical JSON byte representation.
    The output is deterministic and suitable for hashing and signing.
    Specifically, it sorts keys, removes whitespace, and encodes to UTF-8.
    """
    return json.dumps(canonical_dict(obj), sort_keys=True, separators=(',', ':')).encode('utf-8')

def sha256(data: bytes) -> str:
    """
    Calculates the SHA256 hash of the given bytes and returns it as a hexadecimal string.

    Args:
        data (bytes): The input bytes to hash.

    Returns:
        str: The SHA256 hash as a hexadecimal string.
    """
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize().hex()

# ---------- Key Encoding / Decoding ----------

def public_key_bytes(pubkey: Ed25519PublicKey) -> bytes:
    """Alias for public_key_bytes_raw for backward compatibility."""
    return public_key_bytes_raw(pubkey)

def public_key_bytes_raw(pubkey: Ed25519PublicKey) -> bytes:
    """
    Returns the raw bytes of an Ed25519 public key.

    Args:
        pubkey (Ed25519PublicKey): The public key object.

    Returns:
        bytes: The raw byte representation of the public key.
    """
    return pubkey.public_bytes_raw()

def public_key_id_from_raw_bytes(pubkey_raw_bytes: bytes) -> str:
    """
    Generates a unique identifier (SHA256 hex hash) for a public key
    from its raw byte representation. This ID serves as a short,
    consistent identifier for the key.

    Args:
        pubkey_raw_bytes (bytes): The raw byte representation of the public key.

    Returns:
        str: The SHA256 hash of the raw public key bytes as a hexadecimal string.
    """
    return sha256(pubkey_raw_bytes)

def b64encode(data: bytes) -> str:
    """
    Base64-encodes bytes into a URL-safe string.

    Args:
        data (bytes): The bytes to encode.

    Returns:
        str: The base64-encoded string.
    """
    return base64.b64encode(data).decode('ascii')

def b64decode(data: str) -> bytes:
    """
    Base64-decodes a URL-safe string into bytes.

    Args:
        data (str): The base64-encoded string.

    Returns:
        bytes: The decoded bytes.

    Raises:
        binascii.Error: If the input string is not valid base64.
    """
    return base64.b64decode(data)

# ---------- Envelope Model ----------

class GossipEnvelope(BaseModel):
    """
    Represents a signed gossip message envelope, including metadata, payload,
    and cryptographic signature. This Pydantic model ensures type safety
    and structure validation for all envelope fields.

    Fields:
        envelope_version (Literal["1.0"]): The version of the envelope format.
        domain (Literal["blackswan-gossip-v1"]): The domain/protocol identifier.
        payload_type (str): Type identifier for the payload content.
        topic (str): Topic for message routing within the gossip network.

        sender_peer_id (str): Identifier of the sending peer within its local context.
        sender_node_id (str): Global identifier of the sending node.
        sender_pubkey (str): Base64 encoded raw public key of the sender.
        key_id (str): SHA256 hex hash of the sender's raw public key, serving as a key identifier.
        key_version (int): Version of the sender's key, allowing for key rotation.

        seq_no (int): Monotonically increasing sequence number from the sender,
                      used to detect message reordering or loss.
        lamport_ts (int): Lamport timestamp for causal ordering of events across nodes.
        nonce (str): A unique string to prevent replay attacks (e.g., UUID or hash of unique data).
        timestamp_ms (int): UTC timestamp of message creation in milliseconds.

        ttl_ms (int): Time-to-live for the message in milliseconds, after which it should be discarded.
        expires_at_ms (int): UTC timestamp when the message expires in milliseconds.

        parent_hashes (List[str]): List of SHA256 hex hashes of parent messages,
                                   forming a DAG structure for causal dependencies.
        payload_hash (str): SHA256 hex hash of the canonical JSON representation of the payload.
        payload (Any): The actual data content of the gossip message. Can be any JSON-serializable structure.
        signature (str): Base64 encoded Ed25519 signature of the envelope preimage.

        trace_id (Optional[str]): Optional ID for distributed tracing of message flow.
        correlation_id (Optional[str]): Optional ID for correlating related messages across multiple hops.
    """
    envelope_version: Literal[ENVELOPE_VERSION] = ENVELOPE_VERSION
    domain: Literal[DOMAIN_BLACKSWAN_GOSSIP_V1] = DOMAIN_BLACKSWAN_GOSSIP_V1
    payload_type: str
    topic: str

    sender_peer_id: str
    sender_node_id: str
    sender_pubkey: str              # base64 encoded raw public key
    key_id: str                     # hex SHA256 of raw public key bytes
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
    signature: str = ""             # base64 encoded signature

    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None

# ---------- Key Generation ----------

def generate_key_pair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """
    Generates a new Ed25519 private and public key pair.

    Returns:
        tuple[Ed25519PrivateKey, Ed25519PublicKey]: A tuple containing
                                                    the generated private and public keys.
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key

# ---------- Signing and Verification ----------

def sign_envelope(
    payload: Any,
    meta: Dict[str, Any],
    private_key: Ed25519PrivateKey
) -> GossipEnvelope:
    """
    Creates and signs a GossipEnvelope.

    The 'meta' dictionary must contain all fields required by GossipEnvelope,
    except for 'payload', 'payload_hash', and 'signature'.

    'sender_pubkey' and 'key_id' in 'meta' are crucial and are handled as follows:
    - If 'meta['sender_pubkey']' is provided as bytes, it will be base64-encoded.
    - If 'meta['sender_pubkey']' is not provided or is an empty string,
      it will be derived from `private_key.public_key()` and base64-encoded.
    - If 'meta['key_id']' is not provided or is an empty string,
      it will be derived from the raw public key bytes (SHA256 hex).
    - If 'sender_pubkey' (as a base64 string) and 'key_id' (as a hex string) are
      provided in `meta` but do not match the `private_key` provided,
      this function will derive them from `private_key` to ensure consistency
      for signing.

    Args:
        payload (Any): The actual data to be encapsulated in the envelope.
        meta (Dict[str, Any]): A dictionary containing metadata fields for the envelope.
                               Must include `sender_peer_id`, `sender_node_id`, `key_version`,
                               `payload_type`, `topic`, `seq_no`, `lamport_ts`, `nonce`,
                               `timestamp_ms`, `ttl_ms`.
                               `parent_hashes`, `trace_id`, `correlation_id` are optional.
                               `sender_pubkey` and `key_id` will be automatically derived
                               from the `private_key` if not present or inconsistent.
        private_key (Ed25519PrivateKey): The private key used to sign the envelope.

    Returns:
        GossipEnvelope: The fully constructed and signed envelope.

    Raises:
        ValidationError: If the 'meta' dictionary does not contain all required fields
                         or if fields are of incorrect types after processing.
    """
    public_key = private_key.public_key()
    raw_public_key_bytes = public_key_bytes_raw(public_key)
    derived_sender_pubkey_b64 = b64encode(raw_public_key_bytes)
    derived_key_id = public_key_id_from_raw_bytes(raw_public_key_bytes)

    processed_meta = meta.copy()

    # Ensure sender_pubkey is correctly set (base64 string derived from signing key)
    sender_pubkey_val = processed_meta.get('sender_pubkey')
    if isinstance(sender_pubkey_val, bytes):
        processed_meta['sender_pubkey'] = b64encode(sender_pubkey_val)
    if processed_meta.get('sender_pubkey') != derived_sender_pubkey_b64:
        processed_meta['sender_pubkey'] = derived_sender_pubkey_b64

    # Ensure key_id is correctly set (SHA256 hex from raw public key bytes)
    if processed_meta.get('key_id') != derived_key_id:
        processed_meta['key_id'] = derived_key_id

    # Calculate payload hash
    payload_b = canonical_json(payload)
    payload_hash = sha256(payload_b)

    # Create envelope data
    envelope_data = processed_meta
    envelope_data['payload'] = payload
    envelope_data['payload_hash'] = payload_hash
    envelope_data['signature'] = "" # Temporarily empty for preimage calculation

    # Validate and instantiate the envelope model
    try:
        env = GossipEnvelope(**envelope_data)
    except ValidationError as e:
        raise ValidationError(f"Failed to create GossipEnvelope from provided metadata: {e}") from e

    # Sign the preimage (all fields except signature)
    env_dict_for_signing = env.model_dump(exclude={'signature'})
    preimage = canonical_json(env_dict_for_signing)
    sig_bytes = private_key.sign(preimage)
    env.signature = b64encode(sig_bytes)
    return env


def verify_envelope(envelope: GossipEnvelope, public_key: Ed25519PublicKey, seen_nonces: set[str], last_seq: int, now_ms: int) -> tuple[bool, str]:
    """
    Verifies a GossipEnvelope against various criteria to ensure its authenticity, integrity,
    and freshness.

    Checks expiration, replay attacks (nonce), sequence monotonicity,
    payload hash integrity, consistency of sender identity fields, and cryptographic signature.

    Args:
        envelope (GossipEnvelope): The envelope to verify.
        public_key (Ed25519PublicKey): The expected public key of the sender for signature verification.
                                       This key should be retrieved from a trusted source.
        seen_nonces (set[str]): A set of nonces already processed by the receiver to detect replay attacks.
        last_seq (int): The last *valid* sequence number observed from this specific sender node_id.
                        Used to check for monotonicity.
        now_ms (int): The current UTC timestamp in milliseconds.

    Returns:
        tuple[bool, str]: A tuple where the first element is True if the envelope is valid,
                          False otherwise. The second element is an empty string for success,
                          or a reason string for failure.
    """
    if now_ms > envelope.expires_at_ms:
        return False, "expired"

    if envelope.nonce in seen_nonces:
        return False, "replay"

    # NOTE: This check assumes `last_seq` is specific to the `sender_node_id`.
    # It should be maintained per sender to ensure correct monotonic verification.
    if envelope.seq_no <= last_seq:
        return False, f"non-monotonic seq_no: envelope seq_no {envelope.seq_no} is not greater than last seen {last_seq}"

    # Verify payload hash to ensure payload integrity
    actual_payload_hash = sha256(canonical_json(envelope.payload))
    if actual_payload_hash != envelope.payload_hash:
        return False, f"payload hash mismatch: expected {envelope.payload_hash}, got {actual_payload_hash}"

    # Verify sender_pubkey and key_id consistency with the provided public_key.
    # This is a crucial check to prevent an attacker from claiming a false public key
    # while providing a valid signature from a different key.
    expected_pubkey_raw_bytes = public_key_bytes_raw(public_key)
    expected_sender_pubkey_b64 = b64encode(expected_pubkey_raw_bytes)
    expected_key_id = public_key_id_from_raw_bytes(expected_pubkey_raw_bytes)

    if envelope.sender_pubkey != expected_sender_pubkey_b64:
        return False, (
            f"sender_pubkey in envelope does not match provided public_key. "
            f"Expected: {expected_sender_pubkey_b64}, Got: {envelope.sender_pubkey}"
        )
    if envelope.key_id != expected_key_id:
        return False, (
            f"key_id in envelope does not match provided public_key. "
            f"Expected: {expected_key_id}, Got: {envelope.key_id}"
        )

    # Verify signature
    env_dict_for_signing = envelope.model_dump(exclude={'signature'})
    preimage = canonical_json(env_dict_for_signing)
    try:
        signature_bytes = b64decode(envelope.signature)
        public_key.verify(signature_bytes, preimage)
    except (InvalidSignature, BinasciiError) as e:
        # InvalidSignature: signature does not match public key or preimage
        # BinasciiError: envelope.signature is not valid base64
        return False, f"bad signature or malformed base64 signature string: {e}"
    except Exception as e:
        # Catch any other unexpected errors during verification process
        return False, f"unexpected error during signature verification: {type(e).__name__}: {e}"

    return True, ""
