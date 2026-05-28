"""Memory recognition primitives.

Recognition classifies incoming memory-like records before or after storage.
It does not own persistence. It evaluates novelty, familiarity, duplication,
risk, and value using lightweight deterministic heuristics.

The goal is to help the memory swarm decide whether a record is:
- new
- familiar
- duplicate
- suspicious
- dangerous
- valuable
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class RecognitionLabel(str, Enum):
    """Canonical recognition labels."""

    NEW = "new"
    FAMILIAR = "familiar"
    DUPLICATE = "duplicate"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    VALUABLE = "valuable"


@dataclass(frozen=True, slots=True)
class RecognitionSignal:
    """Single reason contributing to a recognition result."""

    name: str
    score: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """Result of classifying an incoming memory record."""

    label: RecognitionLabel
    confidence: float
    novelty_score: float
    familiarity_score: float
    risk_score: float
    value_score: float
    duplicate_of: str = ""
    fingerprint: str = ""
    signals: tuple[RecognitionSignal, ...] = field(default_factory=tuple)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["label"] = self.label.value
        data["signals"] = [signal.to_dict() for signal in self.signals]
        return data


@dataclass(frozen=True, slots=True)
class RecognitionConfig:
    """Tunable thresholds for deterministic memory recognition."""

    duplicate_threshold: float = 0.98
    familiar_threshold: float = 0.45
    valuable_threshold: float = 0.65
    dangerous_threshold: float = 0.75
    suspicious_threshold: float = 0.55
    min_confidence_for_trust: float = 0.5


DANGEROUS_KEYWORDS: frozenset[str] = frozenset(
    {
        "exploit",
        "private_key",
        "seed_phrase",
        "secret",
        "credential",
        "leak",
        "exfiltrate",
        "malware",
        "backdoor",
        "unauthorized",
        "bypass",
        "steal",
        "drain",
        "rug",
        "critical_loss",
        "funds_lost",
    }
)

VALUABLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "verified",
        "success",
        "passed",
        "profitable",
        "improved",
        "regression_fixed",
        "test_green",
        "smoke_ok",
        "validated",
        "milestone",
        "release",
        "architecture",
        "policy",
    }
)

SUSPICIOUS_KEYWORDS: frozenset[str] = frozenset(
    {
        "unknown",
        "untrusted",
        "low_confidence",
        "unsigned",
        "mismatch",
        "unexpected",
        "anomaly",
        "suspicious",
        "degraded",
    }
)


def canonical_fingerprint(record: Any) -> str:
    """Return deterministic fingerprint for a memory-like record."""
    normalized = _normalize_record(record)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class MemoryRecognizer:
    """Deterministic recognizer for memory-like records."""

    def __init__(self, config: RecognitionConfig | None = None) -> None:
        self.config = config or RecognitionConfig()

    def recognize(
        self,
        record: Any,
        existing_records: Iterable[Any] | None = None,
    ) -> RecognitionResult:
        """Classify a record against optional existing memory records."""
        existing = list(existing_records or [])
        fingerprint = canonical_fingerprint(record)

        duplicate_of = ""
        best_similarity = 0.0
        best_existing_id = ""

        record_terms = _record_terms(record)

        for item in existing:
            item_fp = canonical_fingerprint(item)
            item_id = _record_id(item)

            if item_fp == fingerprint:
                best_similarity = 1.0
                best_existing_id = item_id
                duplicate_of = item_id
                break

            similarity = _jaccard(record_terms, _record_terms(item))
            if similarity > best_similarity:
                best_similarity = similarity
                best_existing_id = item_id

        novelty_score = max(0.0, min(1.0, 1.0 - best_similarity))
        familiarity_score = max(0.0, min(1.0, best_similarity))
        risk_score, risk_signals = self._risk_score(record)
        value_score, value_signals = self._value_score(record)

        signals: list[RecognitionSignal] = []
        signals.append(
            RecognitionSignal(
                name="similarity",
                score=familiarity_score,
                detail=best_existing_id,
            )
        )
        signals.extend(risk_signals)
        signals.extend(value_signals)

        label = self._choose_label(
            duplicate_of=duplicate_of,
            familiarity_score=familiarity_score,
            risk_score=risk_score,
            value_score=value_score,
            record=record,
        )

        confidence = self._confidence(
            label=label,
            familiarity_score=familiarity_score,
            risk_score=risk_score,
            value_score=value_score,
            record=record,
        )

        return RecognitionResult(
            label=label,
            confidence=confidence,
            novelty_score=novelty_score,
            familiarity_score=familiarity_score,
            risk_score=risk_score,
            value_score=value_score,
            duplicate_of=duplicate_of,
            fingerprint=fingerprint,
            signals=tuple(signals),
        )

    def _choose_label(
        self,
        *,
        duplicate_of: str,
        familiarity_score: float,
        risk_score: float,
        value_score: float,
        record: Any,
    ) -> RecognitionLabel:
        if duplicate_of or familiarity_score >= self.config.duplicate_threshold:
            return RecognitionLabel.DUPLICATE

        if risk_score >= self.config.dangerous_threshold:
            return RecognitionLabel.DANGEROUS

        if self._is_suspicious(record, risk_score):
            return RecognitionLabel.SUSPICIOUS

        if value_score >= self.config.valuable_threshold:
            return RecognitionLabel.VALUABLE

        if familiarity_score >= self.config.familiar_threshold:
            return RecognitionLabel.FAMILIAR

        return RecognitionLabel.NEW

    def _confidence(
        self,
        *,
        label: RecognitionLabel,
        familiarity_score: float,
        risk_score: float,
        value_score: float,
        record: Any,
    ) -> float:
        record_confidence = _record_confidence(record)

        if label == RecognitionLabel.DUPLICATE:
            base = familiarity_score
        elif label == RecognitionLabel.DANGEROUS:
            base = risk_score
        elif label == RecognitionLabel.SUSPICIOUS:
            base = max(risk_score, 1.0 - record_confidence)
        elif label == RecognitionLabel.VALUABLE:
            base = value_score
        elif label == RecognitionLabel.FAMILIAR:
            base = familiarity_score
        else:
            base = max(0.5, 1.0 - familiarity_score)

        return max(0.0, min(1.0, base))

    def _is_suspicious(self, record: Any, risk_score: float) -> bool:
        if risk_score >= self.config.suspicious_threshold:
            return True

        if _record_confidence(record) < self.config.min_confidence_for_trust:
            return True

        terms = _record_terms(record)
        return bool(terms.intersection(SUSPICIOUS_KEYWORDS))

    def _risk_score(self, record: Any) -> tuple[float, list[RecognitionSignal]]:
        terms = _record_terms(record)
        hits = sorted(terms.intersection(DANGEROUS_KEYWORDS))

        signals: list[RecognitionSignal] = []
        if hits:
            score = min(1.0, 0.45 + 0.15 * len(hits))
            signals.append(
                RecognitionSignal(
                    name="dangerous_keywords",
                    score=score,
                    detail=",".join(hits),
                )
            )
            return score, signals

        return 0.0, signals

    def _value_score(self, record: Any) -> tuple[float, list[RecognitionSignal]]:
        terms = _record_terms(record)
        hits = sorted(terms.intersection(VALUABLE_KEYWORDS))

        signals: list[RecognitionSignal] = []
        score = 0.0

        if hits:
            score = min(1.0, 0.35 + 0.12 * len(hits))
            signals.append(
                RecognitionSignal(
                    name="valuable_keywords",
                    score=score,
                    detail=",".join(hits),
                )
            )

        if _record_verified(record):
            score = max(score, 0.75)
            signals.append(
                RecognitionSignal(
                    name="verified",
                    score=0.75,
                    detail="record verified",
                )
            )

        return score, signals


def _normalize_record(record: Any) -> dict[str, Any]:
    data = _raw_record_dict(record)

    unstable = {
        "id",
        "gid",
        "record_id",
        "created_at",
        "updated_at",
        "timestamp",
        "ts",
        "valid_until",
        "expires_at",
        "signature",
        "verified",
        "priority",
        "metadata",
        "payload_hash",
        "ttl_ms",
        "version",
    }

    normalized = {str(k): v for k, v in data.items() if str(k) not in unstable}

    payload = normalized.get("payload")
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.pop("recognition", None)

        tags = payload.get("tags")
        if isinstance(tags, list):
            filtered_tags = [
                str(tag)
                for tag in tags
                if str(tag).strip()
                and not str(tag).startswith("recognition:")
                and not str(tag).startswith("risk:")
                and not str(tag).startswith("value:")
            ]

            if filtered_tags:
                payload["tags"] = filtered_tags
            else:
                payload.pop("tags", None)

        elif isinstance(tags, str):
            if tags.startswith(("recognition:", "risk:", "value:")):
                payload.pop("tags", None)

        normalized["payload"] = payload

        source = normalized.get("source")
        if isinstance(source, dict):
            source = dict(source)
            source.pop("recognition_label", None)
            source.pop("recognition_confidence", None)
            normalized["source"] = source

        canonical = {
            "kind": normalized.get("kind"),
            "scope": normalized.get("scope"),
            "topic": normalized.get("topic"),
            "payload": normalized.get("payload"),
            "source": normalized.get("source"),
            "confidence": normalized.get("confidence"),
        }

        return {key: value for key, value in canonical.items() if value not in (None, "", {}, [])}


def _raw_record_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        data = record.model_dump()
    elif hasattr(record, "to_dict"):
        data = record.to_dict()
    elif isinstance(record, dict):
        data = dict(record)
    else:
        data = {"value": str(record)}

    return data if isinstance(data, dict) else {"value": str(data)}


def _record_id(record: Any) -> str:
    data = _raw_record_dict(record)
    return str(data.get("id") or data.get("gid") or data.get("record_id") or "")


def _record_confidence(record: Any) -> float:
    data = _raw_record_dict(record)
    try:
        return max(0.0, min(1.0, float(data.get("confidence", 1.0))))
    except (TypeError, ValueError):
        return 1.0


def _record_verified(record: Any) -> bool:
    data = _raw_record_dict(record)
    return bool(data.get("verified", False))


def _record_terms(record: Any) -> set[str]:
    data = _normalize_record(record)
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).lower()

    cleaned = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            cleaned.append(char)
        else:
            cleaned.append(" ")

    return {part.strip() for part in "".join(cleaned).split() if part.strip()}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0

    return len(left.intersection(right)) / float(len(left.union(right)))