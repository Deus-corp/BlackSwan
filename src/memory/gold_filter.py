# src/memory/gold_filter.py
"""
Gold filter – отбирает успешные эпизоды из памяти для будущего обучения.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List
import hashlib


@dataclass
class ExperienceSample:
    instruction: str
    input_text: str
    output_text: str
    score: float
    meta: Dict[str, Any]


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def calculate_success_score(entry: Dict[str, Any]) -> float:
    """
    Простая версия скоринга.
    Позже можно заменить более точной формулой.
    """
    pnl = float(entry.get("pnl_delta", 0.0))
    efficiency = float(entry.get("efficiency", 0.0))
    peer = float(entry.get("peer_validation", 0.0))
    risk_penalty = float(entry.get("risk_penalty", 0.0))

    score = (
        0.50 * pnl +
        0.25 * efficiency +
        0.25 * peer -
        0.40 * risk_penalty
    )

    return max(0.0, min(1.0, score))


def deduplicate_samples(samples: Iterable[ExperienceSample]) -> List[ExperienceSample]:
    seen: set[str] = set()
    result: List[ExperienceSample] = []

    for sample in samples:
        fingerprint = hashlib.sha256(
            f"{_normalize_text(sample.instruction)}\n"
            f"{_normalize_text(sample.input_text)}\n"
            f"{_normalize_text(sample.output_text)}".encode("utf-8")
        ).hexdigest()

        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(sample)

    return result


def filter_gold_samples(
    entries: Iterable[Dict[str, Any]],
    threshold: float = 0.8,
) -> List[ExperienceSample]:
    samples: List[ExperienceSample] = []

    for entry in entries:
        score = calculate_success_score(entry)
        if score < threshold:
            continue

        samples.append(
            ExperienceSample(
                instruction=str(entry.get("task_description", "")),
                input_text=str(entry.get("market_context", "")),
                output_text=str(entry.get("successful_action", "")),
                score=score,
                meta={
                    "event_id": entry.get("event_id"),
                    "node_id": entry.get("node_id"),
                    "source": entry.get("source", "memory"),
                    "adapter_id": entry.get("adapter_id"),
                },
            )
        )

    return deduplicate_samples(samples)