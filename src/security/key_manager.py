"""Centralized secret/key management for node runtime.

Loads signing, Web3, and exchange credentials from environment variables.
Private keys and secrets are never logged.
"""

from __future__ import annotations

import logging
import os
from binascii import Error as BinasciiError
from typing import Final, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

logger = logging.getLogger(__name__)

GOSSIP_KEY_HEX_LENGTH: Final[int] = 64
WEB3_PRIVATE_KEY_HEX_LENGTH_WITHOUT_PREFIX: Final[int] = 64


class KeyManager:
    """Load and provide secure access to runtime key material."""

    __slots__ = (
        "_gossip_private_key",
        "_gossip_key_ephemeral",
        "_web3_private_key_hex",
        "_binance_api_key",
        "_binance_api_secret",
    )

    def __init__(self) -> None:
        self._gossip_private_key: Ed25519PrivateKey
        self._gossip_key_ephemeral = False
        self._web3_private_key_hex: Optional[str] = None
        self._binance_api_key = ""
        self._binance_api_secret = ""

        self.reload()

    def reload(self) -> None:
        """Reload all managed secrets from environment variables."""
        self._load_gossip_key()
        self._load_web3_key()
        self._load_binance_keys()

    @property
    def gossip_key_ephemeral(self) -> bool:
        """True when gossip signing key was generated because env key was missing/invalid."""
        return self._gossip_key_ephemeral

    def get_gossip_private_key(self) -> Ed25519PrivateKey:
        """Return Ed25519 private key used for gossip signing."""
        return self._gossip_private_key

    def get_gossip_public_key_bytes(self) -> bytes:
        """Return raw Ed25519 public key bytes for gossip envelopes."""
        return self._gossip_private_key.public_key().public_bytes_raw()

    def get_gossip_public_key_hex(self) -> str:
        """Return raw Ed25519 public key bytes as hex."""
        return self.get_gossip_public_key_bytes().hex()

    def get_web3_private_key_hex(self) -> str:
        """Return Web3 private key hex string, or empty string when unavailable."""
        return self._web3_private_key_hex or ""

    def get_binance_credentials(self) -> tuple[str, str]:
        """Return Binance testnet API key and secret."""
        return self._binance_api_key, self._binance_api_secret

    def _load_gossip_key(self) -> None:
        raw_value = os.environ.get("GOSSIP_SIGNING_KEY", "")
        key_hex = self._normalize_hex(raw_value, allow_0x=False)

        if key_hex:
            try:
                if len(key_hex) != GOSSIP_KEY_HEX_LENGTH:
                    raise ValueError(
                        f"GOSSIP_SIGNING_KEY must be {GOSSIP_KEY_HEX_LENGTH} hex characters, "
                        f"got {len(key_hex)}"
                    )

                private_bytes = bytes.fromhex(key_hex)
                self._gossip_private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
                self._gossip_key_ephemeral = False
                logger.info("GOSSIP_SIGNING_KEY loaded from environment.")
                return

            except (ValueError, BinasciiError) as exc:
                logger.warning(
                    "Invalid GOSSIP_SIGNING_KEY in environment: %s. Generating ephemeral signing key.",
                    exc,
                )
            except Exception as exc:
                logger.warning(
                    "Unexpected error while loading GOSSIP_SIGNING_KEY: %s. Generating ephemeral signing key.",
                    exc,
                )

        else:
            logger.warning("GOSSIP_SIGNING_KEY not found in environment; generating ephemeral signing key.")

        self._gossip_private_key = Ed25519PrivateKey.generate()
        self._gossip_key_ephemeral = True

    def _load_web3_key(self) -> None:
        raw_value = os.environ.get("WEB3_PRIVATE_KEY", "")
        key_hex = self._normalize_hex(raw_value, allow_0x=True)

        if not key_hex:
            self._web3_private_key_hex = None
            logger.info("WEB3_PRIVATE_KEY not found in environment.")
            return

        if len(key_hex) != WEB3_PRIVATE_KEY_HEX_LENGTH_WITHOUT_PREFIX:
            self._web3_private_key_hex = None
            logger.warning(
                "WEB3_PRIVATE_KEY ignored: expected %s hex characters after optional 0x prefix, got %s.",
                WEB3_PRIVATE_KEY_HEX_LENGTH_WITHOUT_PREFIX,
                len(key_hex),
            )
            return

        try:
            bytes.fromhex(key_hex)
        except ValueError:
            self._web3_private_key_hex = None
            logger.warning("WEB3_PRIVATE_KEY ignored: value is not valid hex.")
            return

        self._web3_private_key_hex = "0x" + key_hex
        logger.info("WEB3_PRIVATE_KEY loaded from environment.")

    def _load_binance_keys(self) -> None:
        self._binance_api_key = str(os.environ.get("BINANCE_TESTNET_API_KEY", "") or "").strip()
        self._binance_api_secret = str(os.environ.get("BINANCE_TESTNET_API_SECRET", "") or "").strip()

        if self._binance_api_key and self._binance_api_secret:
            logger.info("Binance API credentials loaded from environment.")
        else:
            logger.info("Binance API credentials are not fully configured.")

    @staticmethod
    def _normalize_hex(value: str, *, allow_0x: bool) -> str:
        clean = str(value or "").strip()
        if allow_0x and clean.lower().startswith("0x"):
            clean = clean[2:]
        return clean.lower()