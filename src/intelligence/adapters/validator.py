from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal, Optional

from .manifest import AdapterManifest

ValidationStatus = Literal["accepted", "quarantine", "rejected"]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of LoRA adapter manifest validation."""

    status: ValidationStatus
    reasons: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"


class AdapterValidator:
    """Validate LoRA adapter manifests using optional injected policy rules."""

    __slots__ = ("_policy",)

    MAX_RISK_ACCEPT: Final[float] = 0.35
    MAX_RISK_QUARANTINE: Final[float] = 0.75
    REQUIRED_STRING_FIELDS: Final[tuple[str, ...]] = ("name", "version")

    def __init__(self, policy: Optional[Any] = None) -> None:
        self._policy: Final[Optional[Any]] = policy

    def validate(self, manifest: AdapterManifest) -> ValidationResult:
        """Validate a manifest and return accepted/quarantine/rejected."""
        if not isinstance(manifest, AdapterManifest):
            return ValidationResult("rejected", ["manifest must be an AdapterManifest instance"])

        if self._policy is not None:
            policy_result = self._validate_with_policy(manifest)
            if policy_result is not None:
                return policy_result

        reasons: list[str] = []

        for field_name in self.REQUIRED_STRING_FIELDS:
            value = str(getattr(manifest, field_name, "") or "").strip()
            if not value:
                reasons.append(f"missing required field: {field_name}")

        risk = self._safe_float(getattr(manifest, "risk", 0.0), 0.0)
        if risk < 0:
            reasons.append("risk cannot be negative")
        if risk > self.MAX_RISK_QUARANTINE:
            reasons.append(f"risk {risk:.3f} exceeds reject threshold {self.MAX_RISK_QUARANTINE:.3f}")
            return ValidationResult("rejected", reasons)

        if reasons:
            return ValidationResult("rejected", reasons)

        if risk > self.MAX_RISK_ACCEPT:
            return ValidationResult(
                "quarantine",
                [f"risk {risk:.3f} exceeds acceptance threshold {self.MAX_RISK_ACCEPT:.3f}"],
            )

        return ValidationResult("accepted", [])

    def _validate_with_policy(self, manifest: AdapterManifest) -> Optional[ValidationResult]:
        validate = getattr(self._policy, "validate", None)
        if callable(validate):
            result = validate(manifest)
            return self._normalize_policy_result(result)

        if callable(self._policy):
            result = self._policy(manifest)
            return self._normalize_policy_result(result)

        return None

    @staticmethod
    def _normalize_policy_result(result: Any) -> Optional[ValidationResult]:
        if result is None:
            return None

        if isinstance(result, ValidationResult):
            return result

        if isinstance(result, bool):
            return ValidationResult("accepted" if result else "rejected", [] if result else ["policy rejected"])

        if isinstance(result, dict):
            status = str(result.get("status", "")).strip().lower()
            reasons_raw = result.get("reasons", [])
            reasons = [str(reason) for reason in reasons_raw] if isinstance(reasons_raw, list) else [str(reasons_raw)]

            if status in {"accepted", "quarantine", "rejected"}:
                return ValidationResult(status, reasons)  # type: ignore[arg-type]

        return ValidationResult("rejected", [f"invalid policy result: {type(result).__name__}"])

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default