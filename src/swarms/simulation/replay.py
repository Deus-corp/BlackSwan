"""Build simulation replay scenarios from verified runtime evidence memory."""

from __future__ import annotations

import time
import uuid
from typing import Any, Iterable, Mapping


def build_replay_scenario_from_memory_record(
    record: Mapping[str, Any],
    *,
    source: str = "simulation-replay-builder",
) -> dict[str, Any]:
    """Build one replay scenario from a runtime_evidence memory_record."""
    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")

    if record.get("type") != "memory_record":
        raise ValueError("record must have type='memory_record'")

    if str(record.get("kind") or "") != "runtime_evidence":
        raise ValueError("record must have kind='runtime_evidence'")

    status = str(record.get("status") or "unknown").strip().lower()
    if status != "passed":
        raise ValueError("only passed runtime_evidence records can be replayed")

    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    evidence_payload = payload.get("evidence_payload") if isinstance(payload.get("evidence_payload"), Mapping) else {}
    directive = evidence_payload.get("directive") if isinstance(evidence_payload.get("directive"), Mapping) else {}
    result = evidence_payload.get("result") if isinstance(evidence_payload.get("result"), Mapping) else {}

    directive_id = str(payload.get("directive_id") or "").strip()
    evidence_id = str(payload.get("evidence_id") or "").strip()
    action = str(directive.get("action") or "").strip()
    result_status = str(result.get("status") or "").strip()

    scenario_id = f"replay-{directive_id or evidence_id or uuid.uuid4().hex}"

    return {
        "type": "simulation_replay_scenario",
        "scenario_id": scenario_id,
        "source": str(source or "simulation-replay-builder"),
        "subject": str(record.get("subject") or "runtime_directive_seed_check"),
        "status": "pending",
        "replay_kind": "runtime_evidence",
        "directive_id": directive_id or None,
        "evidence_id": evidence_id or None,
        "memory_id": record.get("memory_id") or record.get("id"),
        "action": action or None,
        "expected_result_status": result_status or "applied",
        "payload": {
            "memory_record": _compact_memory_record(record),
            "directive": dict(directive),
            "result": dict(result),
            "checks": list(payload.get("checks") or []),
        },
        "created_at": time.time(),
    }


def build_replay_scenarios_from_memory_records(
    records: Iterable[Any],
    *,
    source: str = "simulation-replay-builder",
) -> list[dict[str, Any]]:
    """Build replay scenarios from all replayable runtime evidence memory records."""
    scenarios: list[dict[str, Any]] = []

    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        try:
            scenarios.append(build_replay_scenario_from_memory_record(record, source=source))
        except (TypeError, ValueError):
            continue

    return scenarios


def _compact_memory_record(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return {
        "memory_id": record.get("memory_id") or record.get("id"),
        "kind": record.get("kind"),
        "status": record.get("status"),
        "subject": record.get("subject"),
        "source": record.get("source"),
        "directive_id": payload.get("directive_id"),
        "evidence_id": payload.get("evidence_id"),
    }


__all__ = [
    "build_replay_scenario_from_memory_record",
    "build_replay_scenarios_from_memory_records",
]