"""
Centralized management for node's private keys.
Loads keys from environment variables and provides methods for secure access.
Private keys are never logged to prevent accidental exposure.
"""
import os
import logging
from typing import Optional, Tuple, Final
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from binascii import Error as BinasciiError # For hex decoding errors

logger = logging.getLogger(__name__)

# Constants
GOSSIP_KEY_HEX_LENGTH: Final[int] = 64 # Ed25519 private keys are 32 bytes, thus 64 hex characters

class KeyManager:
    """
    Manages cryptographic keys for the node, loading them from environment variables
    or generating new ones if not found or invalid. This class centralizes access
    to sensitive key material.

    Attributes:
        _gossip_private_key (Ed25519PrivateKey): The Ed25519 private key for signing gossip messages.
        _web3_private_key_hex (Optional[str]): The Web3 private key as a hexadecimal string.
        _binance_api_key (str): The Binance API key for testnet operations. Defaults to an empty string if not found.
        _binance_api_secret (str): The Binance API secret for testnet operations. Defaults to an empty string if not found.
    """
    _gossip_private_key: Ed25519PrivateKey
    _web3_private_key_hex: Optional[str]
    _binance_api_key: str
    _binance_api_secret: str

    def __init__(self) -> None:
        """
        Initializes the KeyManager by attempting to load keys from specific
        environment variables. If a key (e.g., GOSSIP_SIGNING_KEY) is invalid
        or missing, a new one is generated for immediate use, though a warning
        is logged to alert about the missing/invalid configuration.
        """
        self._load_gossip_key()
        self._load_web3_key()
        self._load_binance_keys()

    def _load_gossip_key(self) -> None:
        """
        Loads the Ed25519 private key for signing gossip messages from the
        `GOSSIP_SIGNING_KEY` environment variable. The key is expected to be
        a 64-character hexadecimal string representing 32 bytes.

        If the environment variable is not set or contains an invalid key
        (e.g., wrong length, invalid hex characters), a new Ed25519 key pair
        is generated, and a warning is logged to indicate the configuration issue.
        """
        gossip_key_hex: Optional[str] = os.environ.get("GOSSIP_SIGNING_KEY")
        if gossip_key_hex:
            try:
                # Ed25519 private keys are 32 bytes, thus 64 hex characters
                if len(gossip_key_hex) != GOSSIP_KEY_HEX_LENGTH:
                    raise ValueError(
                        f"GOSSIP_SIGNING_KEY must be a {GOSSIP_KEY_HEX_LENGTH}-character hex string (32 bytes), "
                        f"but got length {len(gossip_key_hex)}."
                    )
                private_bytes: bytes = bytes.fromhex(gossip_key_hex)
                self._gossip_private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
                logger.info("GOSSIP_SIGNING_KEY loaded successfully from environment.")
            except (ValueError, BinasciiError) as e:
                # ValueError from bytes.fromhex for invalid hex chars or wrong length
                # BinasciiError for other binascii issues, though ValueError is more common for bytes.fromhex
                logger.warning(
                    f"Invalid GOSSIP_SIGNING_KEY found in environment: {e}. "
                    "Generating a new one. Please ensure GOSSIP_SIGNING_KEY is "
                    f"a valid {GOSSIP_KEY_HEX_LENGTH}-character hex string (32 bytes)."
                )
                self._gossip_private_key = Ed25519PrivateKey.generate()
            except Exception as e:
                # Catch any other unexpected errors from cryptography library
                logger.error(
                    f"An unexpected error occurred while loading GOSSIP_SIGNING_KEY: {e}. "
                    "Generating a new key."
                )
                self._gossip_private_key = Ed25519PrivateKey.generate()
        else:
            self._gossip_private_key = Ed25519PrivateKey.generate()
            logger.warning("GOSSIP_SIGNING_KEY not found in environment, generating a new one.")

    def _load_web3_key(self) -> None:
        """
        Loads the Web3 private key (as a hex string) from the `WEB3_PRIVATE_KEY`
        environment variable. This key is intended for blockchain transactions.
        If not found, `_web3_private_key_hex` remains `None`.
        """
        self._web3_private_key_hex = os.environ.get("WEB3_PRIVATE_KEY")
        if self._web3_private_key_hex:
            logger.info("WEB3_PRIVATE_KEY loaded from environment.")
        else:
            logger.info("WEB3_PRIVATE_KEY not found in environment.")

    def _load_binance_keys(self) -> None:
        """
        Loads Binance API keys for testnet operations from environment variables.
        Specifically, `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_API_SECRET`.
        If these variables are not found, they default to empty strings.
        """
        self._binance_api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self._binance_api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
        if self._binance_api_key and self._binance_api_secret:
            logger.info("Binance API credentials loaded successfully from environment.")
        else:
            logger.warning("Binance API credentials (BINANCE_TESTNET_API_KEY/SECRET) not fully configured.")

    def get_gossip_private_key(self) -> Ed25519PrivateKey:
        """
        Returns the Ed25519 private key object used for signing gossip messages.

        Returns:
            Ed25519PrivateKey: The Ed25519 private key.
        """
        return self._gossip_private_key

    def get_gossip_public_key_bytes(self) -> bytes:
        """
        Returns the raw public key bytes corresponding to the gossip private key.
        This format is suitable for embedding directly into gossip message envelopes
        or for deriving public key identifiers.

        Returns:
            bytes: The raw bytes of the Ed25519 public key.
        """
        return self._gossip_private_key.public_key().public_bytes_raw()

    def get_web3_private_key_hex(self) -> str:
        """
        Returns the Web3 private key as a hexadecimal string.

        Returns:
            str: The Web3 private key hex string, or an empty string if not
                 found or set in the environment.
        """
        return self._web3_private_key_hex or ""

    def get_binance_credentials(self) -> Tuple[str, str]:
        """
        Returns the Binance API key and secret as a tuple.

        Returns:
            Tuple[str, str]: A tuple containing the Binance API key and secret.
                             Both elements will be empty strings if credentials
                             were not set in the environment.
        """
        return self._binance_api_key, self._binance_api_secret
