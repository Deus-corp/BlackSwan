"""
CryptoManager – работа с Ed25519 подписями.
Каждый узел генерирует пару ключей при старте.
Публичный ключ используется как Node ID (для проверки подписей).
"""
import json
from cryptography.hazmat.primitives.asymmetric import ed25519

class CryptoManager:
    def __init__(self):
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.public_bytes_hex = self.public_key.public_bytes_raw().hex()

    def sign(self, data: dict) -> str:
        """Подписывает словарь данных (сортировка ключей гарантирует детерминизм)."""
        message = json.dumps(data, sort_keys=True).encode()
        return self.private_key.sign(message).hex()

    @staticmethod
    def verify(data: dict, signature_hex: str, public_key_hex: str) -> bool:
        """Проверяет подпись. Возвращает True, если подпись корректна."""
        try:
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            message = json.dumps(data, sort_keys=True).encode()
            pub_key.verify(bytes.fromhex(signature_hex), message)
            return True
        except Exception:
            return False