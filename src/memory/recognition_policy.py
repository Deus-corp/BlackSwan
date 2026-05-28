"""Policy hooks for memory recognition results.

Recognition answers: "what is this memory?"
Recognition policy answers: "what should the memory swarm do with it?"

This module is intentionally advisory-only. It does not block storage or execute
external actions. It returns action hints that MemorySwarmNode can attach to
records and expose through metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from src.memory.recognition import RecognitionLabel, RecognitionResult


class RecognitionAction(str, Enum):
    """Advisory action hints derived from recognition labels."""

    STORE = "store"
    REVIEW = "review"
    ALERT = "alert"
    DEDUPE_CANDIDATE = "dedupe_candidate"
    COMPRESS_CANDIDATE = "compress_candidate"
    GOLD_CANDIDATE = "gold_candidate"
    QUARANTINE_CANDIDATE = "quarantine_candidate"


@dataclass(frozen=True, slots=True)
class RecognitionDecision:
    """Advisory decision produced from a recognition result."""

    actions: tuple[RecognitionAction, ...]
    severity: str = "info"
    reason: str = "ok"
    labels: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["actions"] = [action.value for action in self.actions]
        return data


@dataclass(frozen=True, slots=True)
class RecognitionPolicyConfig:
    """Thresholds for advisory memory recognition policy."""

    high_risk_threshold: float = 0.75
    medium_risk_threshold: float = 0.5
    high_value_threshold: float = 0.75
    medium_value_threshold: float = 0.5


class MemoryRecognitionPolicy:
    """Convert RecognitionResult into advisory action hints."""

    def __init__(self, config: RecognitionPolicyConfig | None = None) -> None:
        self.config = config or RecognitionPolicyConfig()

    def decide(self, result: RecognitionResult) -> RecognitionDecision:
        """Return advisory actions for a recognition result."""
        actions: list[RecognitionAction] = [RecognitionAction.STORE]
        labels: list[str] = [result.label.value]
        severity = "info"
        reasons: list[str] = []

        if result.label == RecognitionLabel.DANGEROUS:
            actions.extend(
                [
                    RecognitionAction.ALERT,
                    RecognitionAction.REVIEW,
                    RecognitionAction.QUARANTINE_CANDIDATE,
                ]
            )
            severity = "critical"
            reasons.append("dangerous_memory_detected")

        elif result.label == RecognitionLabel.SUSPICIOUS:
            actions.extend(
                [
                    RecognitionAction.REVIEW,
                    RecognitionAction.QUARANTINE_CANDIDATE,
                ]
            )
            severity = "warning"
            reasons.append("suspicious_memory_detected")

        elif result.label == RecognitionLabel.DUPLICATE:
            actions.extend(
                [
                    RecognitionAction.DEDUPE_CANDIDATE,
                    RecognitionAction.COMPRESS_CANDIDATE,
                ]
            )
            severity = "info"
            reasons.append("duplicate_memory_detected")

        elif result.label == RecognitionLabel.VALUABLE:
            actions.append(RecognitionAction.GOLD_CANDIDATE)
            severity = "info"
            reasons.append("valuable_memory_detected")

        elif result.label == RecognitionLabel.FAMILIAR:
            reasons.append("familiar_memory_detected")

        elif result.label == RecognitionLabel.NEW:
            reasons.append("new_memory_detected")

        if result.risk_score >= self.config.high_risk_threshold:
            if RecognitionAction.ALERT not in actions:
                actions.append(RecognitionAction.ALERT)
            if RecognitionAction.REVIEW not in actions:
                actions.append(RecognitionAction.REVIEW)
            severity = "critical"
            labels.append("risk:high")

        elif result.risk_score >= self.config.medium_risk_threshold:
            if RecognitionAction.REVIEW not in actions:
                actions.append(RecognitionAction.REVIEW)
            if severity == "info":
                severity = "warning"
            labels.append("risk:medium")

        if result.value_score >= self.config.high_value_threshold:
            if RecognitionAction.GOLD_CANDIDATE not in actions:
                actions.append(RecognitionAction.GOLD_CANDIDATE)
            labels.append("value:high")

        elif result.value_score >= self.config.medium_value_threshold:
            labels.append("value:medium")

        return RecognitionDecision(
            actions=tuple(dict.fromkeys(actions)),
            severity=severity,
            reason=";".join(reasons) if reasons else "ok",
            labels=tuple(dict.fromkeys(labels)),
        )


DEFAULT_MEMORY_RECOGNITION_POLICY = MemoryRecognitionPolicy()