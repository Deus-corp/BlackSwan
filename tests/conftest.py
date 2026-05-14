# tests/conftest.py
import os
import sys
import pytest

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Сбрасываем переменные окружения, чтобы тесты не влияли друг на друга."""
    monkeypatch.delenv("MARKET_MODE", raising=False)
    monkeypatch.delenv("TOTAL_NODES", raising=False)
    monkeypatch.delenv("PEERS", raising=False)