# src/intelligence/adapters/validator.py
"""
Заглушка валидатора LoRA-адаптеров.
Пока просто пропускает все манифесты.
"""
from dataclasses import dataclass
from typing import Optional
from .manifest import AdapterManifest

@dataclass
class ValidationResult:
    status: str  # "accepted", "quarantine", "rejected"
    reasons: list = None

class AdapterValidator:
    def __init__(self, policy=None):
        self.policy = policy

    def validate(self, manifest: AdapterManifest) -> ValidationResult:
        """Пока всегда accepted."""
        return ValidationResult(status="accepted", reasons=[])