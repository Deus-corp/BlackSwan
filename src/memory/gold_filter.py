from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set, Final


@dataclass(frozen=True, slots=True)
class ExperienceSample:
    """
    Represents an immutable experience sample collected from agent interactions.

    Attributes:
        instruction: The task prompt or instruction.
        input_text: Contextual input provided to the agent.
        output_text: Agent's successful action or response.
        score: Quality score [0.0, 1.0].
        meta: Metadata mapping including provenance information.
    """
    instruction: str
    input_text: str
    output_text: str
    score: float
    meta: Dict[str, Any] = field(default_factory=dict)


def _normalize_text(text: str) -> str:
    """
    Normalizes text by collapsing whitespace and standardizing casing.
    """
    return " ".join(str(text).lower().split())


def calculate_success_score(entry: Dict[str, Any]) -> float:
    """
    Computes a clamped success score [0.0, 1.0] for an experience.
    """
    weights: Final[Dict[str, float]] = {
        "pnl_delta": 0.50,
        "efficiency": 0.25,
        "peer_validation": 0.25,
        "risk_penalty": -0.40
    }
    
    score: float = sum(
        float(entry.get(key, 0.0)) * weight 
        for key, weight in weights.items()
    )
    return max(0.0, min(1.0, score))


def deduplicate_samples(samples: Iterable[ExperienceSample]) -> List[ExperienceSample]:
    """
    Filters unique samples using SHA256 fingerprints based on content.
    """
    seen_fingerprints: Set[str] = set()
    unique_samples: List[ExperienceSample] = []

    for sample in samples:
        fingerprint_source: str = (
            f"{_normalize_text(sample.instruction)}|"
            f"{_normalize_text(sample.input_text)}|"
            f"{_normalize_text(sample.output_text)}"
        )
        fingerprint: str = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()

        if fingerprint not in seen_fingerprints:
            seen_fingerprints.add(fingerprint)
            unique_samples.append(sample)

    return unique_samples


def filter_gold_samples(
    entries: Iterable[Dict[str, Any]],
    threshold: float = 0.8,
) -> List[ExperienceSample]:
    """
    Filters and deduplicates entries that meet the quality threshold.
    """
    gold_samples: List[ExperienceSample] = []

    for entry in entries:
        score: float = calculate_success_score(entry)
        if score < threshold:
            continue

        sample = ExperienceSample(
            instruction=str(entry.get("task_description", "")),
            input_text=str(entry.get("market_context", "")),
            output_text=str(entry.get("successful_action", "")),
            score=score,
            meta={
                "event_id": entry.get("event_id"),
                "node_id": entry.get("node_id"),
                "source": entry.get("source", "memory"),
                "adapter_id": entry.get("adapter_id"),
            }
        )
        gold_samples.append(sample)

    return deduplicate_samples(gold_samples)