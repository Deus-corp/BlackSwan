"""Runtime evidence memory helpers."""

from __future__ import annotations

from typing import Any, Mapping


RUNTIME_EVIDENCE_KIND = "runtime_evidence"


def is_runtime_evidence_record(record: Mapping[str, Any]) -> bool:
    """Return True if a memory_record is runtime evidence."""
    return (
        isinstance(record, Mapping)
        and record.get("type") == "memory_record"
        and str(record.get("kind") or "").strip().lower() == RUNTIME_EVIDENCE_KIND
    )


def classify_runtime_evidence_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a runtime_evidence memory record for memory policy."""
    if not is_runtime_evidence_record(record):
        return {
            "is_runtime_evidence": False,
            "valuable": False,
            "gold_candidate": False,
            "review_candidate": False,
            "alert_candidate": False,
            "reason": "not_runtime_evidence",
            "tags": [],
        }

    status = str(record.get("status") or "").strip().lower()
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    directive_id = str(payload.get("directive_id") or "").strip()

    passed_checks = sum(
        1
        for item in checks
        if isinstance(item, Mapping) and str(item.get("status") or "").lower() == "passed"
    )
    total_checks = len(checks)

    valuable = status == "passed" and total_checks > 0 and passed_checks == total_checks
    alert = status == "failed"
    review = status in {"partial", "unknown"} or (total_checks > 0 and passed_checks < total_checks and not alert)

    tags = ["runtime_evidence", f"status:{status or 'unknown'}"]
    if directive_id:
        tags.append(f"directive:{directive_id}")
    if valuable:
        tags.append("gold_candidate")
    if review:
        tags.append("review_candidate")
    if alert:
        tags.append("alert_candidate")

    return {
        "is_runtime_evidence": True,
        "valuable": valuable,
        "gold_candidate": valuable,
        "review_candidate": review,
        "alert_candidate": alert,
        "reason": _reason(status=status, valuable=valuable, review=review, alert=alert),
        "directive_id": directive_id or None,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "tags": tags,
    }


def enrich_runtime_evidence_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return memory record copy enriched with runtime evidence classification."""
    enriched = dict(record)
    classification = classify_runtime_evidence_record(record)

    payload = dict(enriched.get("payload") or {}) if isinstance(enriched.get("payload"), Mapping) else {}
    payload["runtime_evidence_classification"] = classification
    enriched["payload"] = payload

    tags = list(enriched.get("tags") or []) if isinstance(enriched.get("tags"), list) else []
    for tag in classification.get("tags", []):
        if tag not in tags:
            tags.append(tag)
    enriched["tags"] = tags

    if classification.get("gold_candidate"):
        enriched["importance"] = max(float(enriched.get("importance") or 0.0), 0.9)
    elif classification.get("alert_candidate"):
        enriched["importance"] = max(float(enriched.get("importance") or 0.0), 0.8)

    return enriched


def _reason(*, status: str, valuable: bool, review: bool, alert: bool) -> str:
    if valuable:
        return "runtime_evidence_passed_all_checks"
    if alert:
        return "runtime_evidence_failed"
    if review:
        return "runtime_evidence_needs_review"
    return f"runtime_evidence_status_{status or 'unknown'}"


__all__ = [
    "RUNTIME_EVIDENCE_KIND",
    "classify_runtime_evidence_record",
    "enrich_runtime_evidence_record",
    "is_runtime_evidence_record",
]