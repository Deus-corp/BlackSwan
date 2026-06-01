"""Memory summary utilities.

This module builds compact operational summaries from memory records and
recognition counters. The summary is intended for MemorySwarmNode heartbeat,
Overseer, dashboard, and future autonomous decision policies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from src.memory.gold_filter import select_gold_memory_samples
from src.memory.runtime_evidence import classify_runtime_evidence_record


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
    runtime_evidence_gold_candidates: int = 0
    runtime_evidence_review_candidates: int = 0
    runtime_evidence_alert_candidates: int = 0
    runtime_evidence_records: int = 0
    replay_execution_evidence_records: int = 0
    replay_execution_evidence_passed: int = 0
    replay_execution_evidence_failed: int = 0

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

    runtime_evidence_records = 0
    runtime_evidence_gold_candidates = 0
    runtime_evidence_review_candidates = 0
    runtime_evidence_alert_candidates = 0
    replay_execution_evidence_records = 0
    replay_execution_evidence_passed = 0
    replay_execution_evidence_failed = 0

    by_kind: dict[str, int] = {}
    by_scope: dict[str, int] = {}

    inferred_recognition_counts: dict[str, int] = {}
    inferred_action_counts: dict[str, int] = {}

    for record in record_list:
        data = _record_to_dict(record)

        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        effective_kind = str(data.get("kind") or payload.get("kind") or "unknown")
        effective_scope = str(data.get("scope") or payload.get("scope") or "unknown")
        effective_status = str(data.get("status") or payload.get("status") or "").strip().lower()
        effective_subject = str(data.get("subject") or payload.get("subject") or "").strip()

        by_kind[effective_kind] = by_kind.get(effective_kind, 0) + 1
        by_scope[effective_scope] = by_scope.get(effective_scope, 0) + 1

        evidence_subject = effective_subject

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

        classifier_record = dict(data)
        classifier_record["kind"] = effective_kind
        classifier_record["status"] = effective_status
        if effective_subject:
            classifier_record["subject"] = effective_subject
        classifier_record["payload"] = payload

        runtime_evidence = classify_runtime_evidence_record(classifier_record)
        if runtime_evidence.get("is_runtime_evidence"):
            runtime_evidence_records += 1
            if runtime_evidence.get("gold_candidate"):
                runtime_evidence_gold_candidates += 1
            if runtime_evidence.get("review_candidate"):
                runtime_evidence_review_candidates += 1
            if runtime_evidence.get("alert_candidate"):
                runtime_evidence_alert_candidates += 1

            if evidence_subject == "simulation_replay_execution_check":
                replay_execution_evidence_records += 1
                if effective_status == "passed":
                    replay_execution_evidence_passed += 1
                elif effective_status == "failed":
                    replay_execution_evidence_failed += 1

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
        runtime_evidence_records=runtime_evidence_records,
        runtime_evidence_gold_candidates=runtime_evidence_gold_candidates,
        runtime_evidence_review_candidates=runtime_evidence_review_candidates,
        runtime_evidence_alert_candidates=runtime_evidence_alert_candidates,
        replay_execution_evidence_records=replay_execution_evidence_records,
        replay_execution_evidence_passed=replay_execution_evidence_passed,
        replay_execution_evidence_failed=replay_execution_evidence_failed,
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