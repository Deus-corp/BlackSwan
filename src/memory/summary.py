"""Memory summary utilities.

This module builds compact operational summaries from memory records and
recognition counters. The summary is intended for MemorySwarmNode heartbeat,
Overseer, dashboard, and future autonomous decision policies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from src.memory.gold_filter import select_gold_memory_samples


@dataclass(frozen=True, slots=True)
class MemorySummary:
    """Compact operational summary of memory state."""

    total_records: int = 0
    recognized_records: int = 0
    gold_candidates: int = 0
    review_candidates: int = 0
    alert_candidates: int = 0
    dedupe_candidates: int = 0
    compress_candidates: int = 0
    quarantine_candidates: int = 0
    recognition_counts: dict[str, int] = field(default_factory=dict)
    recognition_action_counts: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    by_scope: dict[str, int] = field(default_factory=dict)
    degraded: bool = False
    reason: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_memory_summary(
    records: Iterable[Any],
    *,
    recognition_counts: dict[str, int] | None = None,
    recognition_action_counts: dict[str, int] | None = None,
    total_records: int | None = None,
    degraded: bool = False,
    reason: str = "ok",
) -> MemorySummary:
    """Build MemorySummary from records and optional runtime counters."""
    record_list = list(records or [])

    by_kind: dict[str, int] = {}
    by_scope: dict[str, int] = {}

    inferred_recognition_counts: dict[str, int] = {}
    inferred_action_counts: dict[str, int] = {}

    for record in record_list:
        data = _record_to_dict(record)

        kind = str(data.get("kind") or "unknown")
        scope = str(data.get("scope") or "unknown")

        by_kind[kind] = by_kind.get(kind, 0) + 1
        by_scope[scope] = by_scope.get(scope, 0) + 1

        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            continue

        recognition = payload.get("recognition", {})
        if isinstance(recognition, dict):
            label = str(recognition.get("label") or "").strip()
            if label:
                inferred_recognition_counts[label] = inferred_recognition_counts.get(label, 0) + 1

        policy = payload.get("recognition_policy", {})
        if isinstance(policy, dict):
            actions = policy.get("actions", [])
            if isinstance(actions, str):
                actions = [actions]
            if isinstance(actions, list):
                for action in actions:
                    clean_action = str(action or "").strip()
                    if clean_action:
                        inferred_action_counts[clean_action] = inferred_action_counts.get(clean_action, 0) + 1

    final_recognition_counts = dict(inferred_recognition_counts)
    final_recognition_counts.update(recognition_counts or {})

    final_action_counts = dict(inferred_action_counts)
    final_action_counts.update(recognition_action_counts or {})

    gold_samples = select_gold_memory_samples(record_list)

    return MemorySummary(
        total_records=int(total_records if total_records is not None else len(record_list)),
        recognized_records=sum(final_recognition_counts.values()),
        gold_candidates=max(
            len(gold_samples),
            int(final_action_counts.get("gold_candidate", 0)),
        ),
        review_candidates=int(final_action_counts.get("review", 0)),
        alert_candidates=int(final_action_counts.get("alert", 0)),
        dedupe_candidates=int(final_action_counts.get("dedupe_candidate", 0)),
        compress_candidates=int(final_action_counts.get("compress_candidate", 0)),
        quarantine_candidates=int(final_action_counts.get("quarantine_candidate", 0)),
        recognition_counts=final_recognition_counts,
        recognition_action_counts=final_action_counts,
        by_kind=by_kind,
        by_scope=by_scope,
        degraded=bool(degraded),
        reason=str(reason or "ok"),
    )


def _record_to_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        data = record.model_dump()
    elif hasattr(record, "to_dict"):
        data = record.to_dict()
    elif isinstance(record, dict):
        data = dict(record)
    else:
        data = {"value": str(record)}

    return data if isinstance(data, dict) else {"value": str(data)}