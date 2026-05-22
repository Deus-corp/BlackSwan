"""
CryptoManager – Handles Ed25519 digital signatures for nodes.

Each node generates a unique Ed25519 key pair upon initialization.
The hexadecimal representation of the public key serves as the node's unique identifier (Node ID),
which is crucial for verifying signatures and establishing trust within the system.
"""

import json
import logging
from typing import Any, Dict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger(__name__)

class CryptoManager:
    """
    Manages cryptographic operations, specifically Ed25519 key generation,
    signing data, and verifying signatures.
    """

    __slots__ = ("_private_key", "public_key", "public_bytes_hex")

    def __init__(self) -> None:
        """
        Initializes the CryptoManager by generating a new Ed25519 key pair.
        """
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self._private_key.public_key()
        self.public_bytes_hex = self.public_key.public_bytes_raw().hex()

    @staticmethod
    def _serialize_data(data: Dict[str, Any]) -> bytes:
        """
        Serializes data to a deterministic JSON byte string.
        """
        return json.dumps(data, sort_keys=True).encode("utf-8")

    def sign(self, data: Dict[str, Any]) -> str:
        """
        Digitally signs a dictionary of data using the node's private key.

        Args:
            data: A dictionary containing the data to be signed.

        Returns:
            A hexadecimal string representation of the signature.
        """
        message = self._serialize_data(data)
        signature = self._private_key.sign(message)
        return signature.hex()

    @staticmethod
    def verify(data: Dict[str, Any], signature_hex: str, public_key_hex: str) -> bool:
        """
        Verifies a digital signature against a dictionary of data and a public key.

        Args:
            data: The dictionary of data that was originally signed.
            signature_hex: The hexadecimal string representation of the signature.
            public_key_hex: The hexadecimal string representation of the public key.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            public_bytes = bytes.fromhex(public_key_hex)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            
            message = CryptoManager._serialize_data(data)
            signature = bytes.fromhex(signature_hex)
            
            pub_key.verify(signature, message)
            return True
        except (ValueError, TypeError, InvalidSignature) as e:
            logger.warning(
                "Signature verification failed for key '%s...': %s: %s",
                public_key_hex[:16],
                type(e).__name__,
                e,
            )
            return False
        except Exception:
            logger.exception(
                "Unexpected error during signature verification for key '%s...'",
                public_key_hex[:16],
            )
            return False