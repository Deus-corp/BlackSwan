from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal, Optional, List
from .manifest import AdapterManifest

#: Represents valid states for an adapter manifest post-validation.
ValidationStatus = Literal["accepted", "quarantine", "rejected"]

@dataclass(frozen=True, slots=True)
class ValidationResult:
    """
    Outcome of a LoRA-adapter manifest validation process.

    Attributes:
        status: The determined state of the manifest validation.
        reasons: A list of human-readable strings explaining the status, if applicable.
    """
    status: ValidationStatus
    reasons: List[str] = field(default_factory=list)

class AdapterValidator:
    """
    Validator implementation for LoRA-adapter manifests.

    This class serves as the orchestrator for manifest validation logic. It is
    designed to support injection of specific validation policies while providing
    a default permissive implementation.
    """

    __slots__ = ("_policy",)

    def __init__(self, policy: Optional[Any] = None) -> None:
        """
        Initializes the validator with an optional policy object.

        Args:
            policy: An optional rule set or configuration object to influence
                the validation logic.
        """
        self._policy: Final[Optional[Any]] = policy

    def validate(self, manifest: AdapterManifest) -> ValidationResult:
        """
        Evaluates the provided manifest against current validation policies.

        Args:
            manifest: The LoRA-adapter manifest instance to evaluate.

        Returns:
            A ValidationResult detailing the outcome of the evaluation.
        """
        # Default implementation: Accepts all manifests.
        return ValidationResult(status="accepted", reasons=[])