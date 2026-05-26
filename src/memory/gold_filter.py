from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Final, Iterable


@dataclass(frozen=True, slots=True)
class ExperienceSample:
    """Immutable high-quality experience sample for training/export."""

    instruction: str
    input_text: str
    output_text: str
    score: float
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "instruction", str(self.instruction or ""))
        object.__setattr__(self, "input_text", str(self.input_text or ""))
        object.__setattr__(self, "output_text", str(self.output_text or ""))
        object.__setattr__(self, "score", _clamp(_safe_float(self.score), 0.0, 1.0))

        if not isinstance(self.meta, dict):
            object.__setattr__(self, "meta", {"raw_meta": self.meta})
        else:
            object.__setattr__(self, "meta", dict(self.meta))

    @property
    def fingerprint(self) -> str:
        return sample_fingerprint(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "input_text": self.input_text,
            "output_text": self.output_text,
            "score": self.score,
            "meta": dict(self.meta),
        }


SCORING_WEIGHTS: Final[dict[str, float]] = {
    "pnl_delta": 0.50,
    "efficiency": 0.25,
    "peer_validation": 0.25,
    "risk_penalty": -0.40,
}

DEFAULT_THRESHOLD: Final[float] = 0.8


def calculate_success_score(entry: dict[str, Any]) -> float:
    """Compute a clamped success score in [0.0, 1.0]."""
    if not isinstance(entry, dict):
        return 0.0

    score = 0.0
    for key, weight in SCORING_WEIGHTS.items():
        score += _safe_float(entry.get(key), 0.0) * weight

    return _clamp(score, 0.0, 1.0)


def deduplicate_samples(samples: Iterable[ExperienceSample]) -> list[ExperienceSample]:
    """Return unique samples by content fingerprint, preserving first occurrence."""
    seen: set[str] = set()
    unique_samples: list[ExperienceSample] = []

    for sample in samples:
        if not isinstance(sample, ExperienceSample):
            continue

        fingerprint = sample.fingerprint
        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        unique_samples.append(sample)

    return unique_samples


def filter_gold_samples(
    entries: Iterable[dict[str, Any]],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[ExperienceSample]:
    """Filter raw entries into deduplicated gold experience samples."""
    safe_threshold = _clamp(_safe_float(threshold, DEFAULT_THRESHOLD), 0.0, 1.0)
    gold_samples: list[ExperienceSample] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        score = calculate_success_score(entry)
        if score < safe_threshold:
            continue

        instruction = str(entry.get("task_description", "") or "").strip()
        input_text = str(entry.get("market_context", "") or "").strip()
        output_text = str(entry.get("successful_action", "") or "").strip()

        if not instruction or not output_text:
            continue

        sample = ExperienceSample(
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            score=score,
            meta={
                "event_id": entry.get("event_id"),
                "node_id": entry.get("node_id"),
                "source": entry.get("source", "memory"),
                "adapter_id": entry.get("adapter_id"),
                "fingerprint_source": "task_description|market_context|successful_action",
            },
        )
        gold_samples.append(sample)

    return deduplicate_samples(gold_samples)


def sample_fingerprint(sample: ExperienceSample) -> str:
    """Return deterministic SHA256 fingerprint for an experience sample."""
    fingerprint_source = (
        f"{_normalize_text(sample.instruction)}|"
        f"{_normalize_text(sample.input_text)}|"
        f"{_normalize_text(sample.output_text)}"
    )
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    """Normalize text for stable deduplication."""
    return " ".join(str(text or "").lower().split())


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    return number if math.isfinite(number) else default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))