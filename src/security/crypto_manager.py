"""CryptoManager – Ed25519 signing and verification helpers for swarm nodes."""

from __future__ import annotations

import json
import logging
from typing import Any, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger(__name__)


class CryptoManager:
    """Manage Ed25519 key generation, deterministic signing, and verification."""

    __slots__ = ("_private_key", "public_key", "public_bytes_hex")

    PUBLIC_KEY_BYTES: Final[int] = 32
    SIGNATURE_BYTES: Final[int] = 64

    def __init__(self, private_key_hex: str | None = None) -> None:
        """Create a manager from an existing private key hex or generate a new key."""
        if private_key_hex:
            self._private_key = self.private_key_from_hex(private_key_hex)
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()

        self.public_key = self._private_key.public_key()
        self.public_bytes_hex = self.public_key.public_bytes_raw().hex()

    @property
    def private_bytes_hex(self) -> str:
        """Return raw private key bytes as hex.

        Use carefully: this is secret material and should not be logged.
        """
        return self._private_key.private_bytes_raw().hex()

    def sign(self, data: dict[str, Any]) -> str:
        """Sign a dictionary and return a hex-encoded Ed25519 signature."""
        message = self._serialize_data(data)
        return self._private_key.sign(message).hex()

    def sign_bytes(self, data: bytes) -> str:
        """Sign raw bytes and return a hex-encoded Ed25519 signature."""
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        return self._private_key.sign(data).hex()

    @classmethod
    def from_private_key_hex(cls, private_key_hex: str) -> CryptoManager:
        """Build a manager from a raw 32-byte Ed25519 private key hex string."""
        return cls(private_key_hex=private_key_hex)

    @staticmethod
    def verify(data: dict[str, Any], signature_hex: str, public_key_hex: str) -> bool:
        """Verify a dictionary signature against a hex-encoded Ed25519 public key."""
        try:
            message = CryptoManager._serialize_data(data)
            return CryptoManager.verify_bytes(message, signature_hex, public_key_hex)
        except Exception as exc:
            logger.warning("Signature verification input serialization failed: %s", exc)
            return False

    @staticmethod
    def verify_bytes(data: bytes, signature_hex: str, public_key_hex: str) -> bool:
        """Verify raw bytes against a hex-encoded signature and public key."""
        try:
            if not isinstance(data, bytes):
                raise TypeError("data must be bytes")

            public_bytes = bytes.fromhex(str(public_key_hex or "").strip())
            signature = bytes.fromhex(str(signature_hex or "").strip())

            if len(public_bytes) != CryptoManager.PUBLIC_KEY_BYTES:
                raise ValueError(f"public key must be {CryptoManager.PUBLIC_KEY_BYTES} bytes")
            if len(signature) != CryptoManager.SIGNATURE_BYTES:
                raise ValueError(f"signature must be {CryptoManager.SIGNATURE_BYTES} bytes")

            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            public_key.verify(signature, data)
            return True

        except InvalidSignature:
            logger.warning("Signature verification failed for key '%s...': InvalidSignature", str(public_key_hex)[:16])
            return False
        except (ValueError, TypeError) as exc:
            logger.warning("Signature verification failed for key '%s...': %s", str(public_key_hex)[:16], exc)
            return False
        except Exception:
            logger.exception("Unexpected error during signature verification for key '%s...'", str(public_key_hex)[:16])
            return False

    @staticmethod
    def public_key_from_hex(public_key_hex: str) -> ed25519.Ed25519PublicKey:
        """Decode an Ed25519 public key from raw 32-byte hex."""
        public_bytes = bytes.fromhex(str(public_key_hex or "").strip())
        if len(public_bytes) != CryptoManager.PUBLIC_KEY_BYTES:
            raise ValueError(f"public key must be {CryptoManager.PUBLIC_KEY_BYTES} bytes")
        return ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)

    @staticmethod
    def private_key_from_hex(private_key_hex: str) -> ed25519.Ed25519PrivateKey:
        """Decode an Ed25519 private key from raw 32-byte hex."""
        private_bytes = bytes.fromhex(str(private_key_hex or "").strip())
        if len(private_bytes) != CryptoManager.PUBLIC_KEY_BYTES:
            raise ValueError(f"private key must be {CryptoManager.PUBLIC_KEY_BYTES} bytes")
        return ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)

    @staticmethod
    def _serialize_data(data: dict[str, Any]) -> bytes:
        """Serialize dictionary data to canonical UTF-8 JSON bytes."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")

        return json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")