from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal, Optional, List
from .manifest import AdapterManifest

ValidationStatus = Literal["accepted", "quarantine", "rejected"]

@dataclass(frozen=True, slots=True)
class ValidationResult:
    """
    Represents the outcome of a LoRA-adapter manifest validation.

    Attributes:
        status: The validation status (accepted, quarantine, or rejected).
        reasons: A list of descriptive reasons if status is not 'accepted'.
    """
    status: ValidationStatus
    reasons: List[str] = field(default_factory=list)

class AdapterValidator:
    """
    Validator implementation for LoRA-adapter manifests.

    This class acts as a template for manifest validation. Currently,
    it provides a pass-through implementation but is structured to
    support pluggable validation policies in future iterations.
    """

    __slots__ = ("_policy",)

    def __init__(self, policy: Optional[Any] = None) -> None:
        """
        Initializes the validator with an optional policy.

        Args:
            policy: Configuration or rule set to guide validation logic.
        """
        self._policy: Final[Optional[Any]] = policy

    def validate(self, manifest: AdapterManifest) -> ValidationResult:
        """
        Executes validation logic on the provided manifest.

        Args:
            manifest: The LoRA-adapter manifest to evaluate.

        Returns:
            A ValidationResult object containing the outcome of the process.
        """
        return ValidationResult(status="accepted", reasons=[])