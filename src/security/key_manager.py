# src/security/key_manager.py
"""
Централизованное управление приватными ключами узла.
Загружает ключи из переменных окружения и предоставляет методы доступа.
Никогда не логирует приватный ключ.
"""
import os
import logging
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

logger = logging.getLogger(__name__)

class KeyManager:
    def __init__(self):
        # Gossip signing key (для подписи геномов)
        gossip_key_hex = os.environ.get("GOSSIP_SIGNING_KEY")
        if gossip_key_hex:
            try:
                self.gossip_private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(gossip_key_hex))
            except Exception:
                logger.warning("Invalid GOSSIP_SIGNING_KEY, generating new one")
                self.gossip_private_key = Ed25519PrivateKey.generate()
        else:
            self.gossip_private_key = Ed25519PrivateKey.generate()

        # Web3 private key (для блокчейн-транзакций)
        web3_key_hex = os.environ.get("WEB3_PRIVATE_KEY")
        self.web3_private_key = web3_key_hex  # храним как hex-строку, если нужна

        # Binance API keys (для тестнета – не так критично, но всё же)
        self.binance_api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.binance_api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

    def get_gossip_private_key(self) -> Ed25519PrivateKey:
        """Возвращает приватный ключ для подписи gossip-сообщений."""
        return self.gossip_private_key

    def get_gossip_public_key_bytes(self) -> bytes:
        """Возвращает публичный ключ в бинарном виде (для вставки в gossip-сообщения)."""
        return self.gossip_private_key.public_key().public_bytes_raw()

    def get_web3_private_key_hex(self) -> str:
        """Возвращает приватный ключ для Web3 (если задан)."""
        return self.web3_private_key or ""

    def get_binance_credentials(self) -> tuple[str, str]:
        """Возвращает API ключи Binance."""
        return self.binance_api_key, self.binance_api_secret