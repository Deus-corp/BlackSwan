"""
CryptoManager – Handles Ed25519 digital signatures for nodes.

Each node generates a unique Ed25519 key pair upon initialization.
The hexadecimal representation of the public key serves as the node's unique identifier (Node ID),
which is crucial for verifying signatures and establishing trust within the system.
"""
import json
from typing import Dict, Any
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

class CryptoManager:
    """
    Manages cryptographic operations, specifically Ed25519 key generation,
    signing data, and verifying signatures.
    """

    def __init__(self):
        """
        Initializes the CryptoManager by generating a new Ed25519 key pair.
        The public key is stored in its raw hexadecimal format, serving as the node's identifier.
        """
        self.private_key: ed25519.Ed25519PrivateKey = ed25519.Ed25519PrivateKey.generate()
        self.public_key: ed25519.Ed25519PublicKey = self.private_key.public_key()
        self.public_bytes_hex: str = self.public_key.public_bytes_raw().hex()

    def sign(self, data: Dict[str, Any]) -> str:
        """
        Digitally signs a dictionary of data using the node's private key.
        The data is first serialized to a JSON string with sorted keys to ensure deterministic
        hashing and consistency across signing and verification.

        Args:
            data: A dictionary containing the data to be signed.

        Returns:
            A hexadecimal string representation of the signature.
        """
        message: bytes = json.dumps(data, sort_keys=True).encode('utf-8')
        signature: bytes = self.private_key.sign(message)
        return signature.hex()

    @staticmethod
    def verify(data: Dict[str, Any], signature_hex: str, public_key_hex: str) -> bool:
        """
        Verifies a digital signature against a dictionary of data and a public key.
        The data is serialized in the same deterministic way as during signing.

        Args:
            data: The dictionary of data that was originally signed.
            signature_hex: The hexadecimal string representation of the signature.
            public_key_hex: The hexadecimal string representation of the public key
                            to use for verification.

        Returns:
            True if the signature is valid for the given data and public key, False otherwise.
        """
        try:
            pub_key: ed25519.Ed25519PublicKey = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            message: bytes = json.dumps(data, sort_keys=True).encode('utf-8')
            signature: bytes = bytes.fromhex(signature_hex)
            pub_key.verify(signature, message)
            return True
        except (ValueError, InvalidSignature) as e:
            # ValueError: Indicates an issue with hex decoding or incorrect byte lengths for keys/signatures.
            # InvalidSignature: Indicates that the signature does not match the data and public key.
            # Consider adding logging here: logging.warning(f"Signature verification failed: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected errors during the process, e.g., cryptographic library issues.
            # Consider adding logging here: logging.error(f"An unexpected error occurred during signature verification: {e}")
            return False