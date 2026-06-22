from __future__ import annotations

from src.testing import swarm_runtime_smoke


def test_improver_provider_gate_false_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert swarm_runtime_smoke._improver_llm_provider_available() is False


def test_improver_provider_gate_true_with_gemini_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert swarm_runtime_smoke._improver_llm_provider_available() is True


def test_improver_provider_gate_true_with_google_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert swarm_runtime_smoke._improver_llm_provider_available() is True


def test_improver_provider_gate_true_with_deepseek_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")

    assert swarm_runtime_smoke._improver_llm_provider_available() is True


def test_skip_improver_agent_smoke_true_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert swarm_runtime_smoke._skip_improver_agent_smoke("test improver check") is True