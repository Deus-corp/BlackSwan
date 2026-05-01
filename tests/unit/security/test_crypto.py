import pytest
from src.security.crypto_manager import CryptoManager

def test_sign_and_verify():
    crypto = CryptoManager()
    data = {"params": {"x": 0.5}, "fitness": 0.9}
    sig = crypto.sign(data)
    assert CryptoManager.verify(data, sig, crypto.public_bytes_hex)

def test_tampered_data_fails():
    crypto = CryptoManager()
    data = {"params": {"x": 0.5}, "fitness": 0.9}
    sig = crypto.sign(data)
    data["fitness"] = 0.1  # подмена
    assert not CryptoManager.verify(data, sig, crypto.public_bytes_hex)