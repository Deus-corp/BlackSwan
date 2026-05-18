# src/intelligence/adapters/validator.py
"""
Заглушка валидатора LoRA-адаптеров.
Пока просто пропускает все манифесты.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any
from .manifest import AdapterManifest

@dataclass
class ValidationResult:
    """
    Represents the result of validating an adapter manifest.
    """
    status: str  # "accepted", "quarantine", "rejected"
    reasons: List[str] = field(default_factory=list) # Changed to use field(default_factory=list) for mutable default

class AdapterValidator:
    """
    A placeholder validator for LoRA adapter manifests.
    Currently, it accepts all manifests without actual validation.
    """
    def __init__(self, policy: Optional[Any] = None) -> None:
        """
        Initializes the AdapterValidator.

        Args:
            policy (Optional[Any]): The validation policy to use.
                                     Currently not utilized.
        """
        self.policy = policy

    def validate(self, manifest: AdapterManifest) -> ValidationResult:
        """
        Validates the given adapter manifest.
        Currently, always returns an "accepted" status.

        Args:
            manifest (AdapterManifest): The adapter manifest to validate.

        Returns:
            ValidationResult: The result of the validation.
        """
        return ValidationResult(status="accepted", reasons=[])