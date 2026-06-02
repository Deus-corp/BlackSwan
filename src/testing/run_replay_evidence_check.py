"""Run the controlled replay evidence lifecycle check end-to-end."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any, Mapping

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter
from src.testing.evidence_memory_bridge import publish_evidence_memory_records
from src.testing.publish_replay_execution_evidence import publish_replay_execution_evidence
from src.testing.seed_directive import seed_directive
from src.testing.seed_replay_scenario import seed_replay_scenario
from src.memory.summary import build_memory_summary
from src.swarms.security.runtime_validation import build_security_validation_heartbeat_metrics

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run replay evidence lifecycle check.")
    parser.add_argument(
        "--scenario-id",
        default="replay-runtime-reduce-risk-1",
        help="Replay scenario id.",
    )
    parser.add_argument("--action", default="REDUCE_RISK", help="Replay action.")
    parser.add_argument(
        "--directive-id",
        default="runtime-run-replay-e2e-1",
        help="RUN_REPLAY directive id.",
    )
    parser.add_argument(
        "--source",
        default="replay-evidence-check",
        help="Source used for generated helper records where applicable.",
    )
    parser.add_argument(
        "--expected-result-status",
        default="applied",
        help="Expected original directive result status for the replay scenario.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=10.0,
        help="Maximum seconds to wait for simulation_replay_execution.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Polling interval while waiting for simulation_replay_execution.",
    )
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    return parser


async def run_replay_evidence_check(args: argparse.Namespace) -> dict[str, Any]:
    db_path = str(args.db_path or config.crdt_db_path)
    scenario_id = str(args.scenario_id or "").strip()
    directive_id = str(args.directive_id or "").strip()

    if not scenario_id:
        raise ValueError("scenario-id is required")
    if not directive_id:
        raise ValueError("directive-id is required")

    source = str(args.source or "replay-evidence-check")

    scenario = await seed_replay_scenario(
        argparse.Namespace(
            scenario_id=scenario_id,
            action=str(args.action or "REDUCE_RISK"),
            expected_result_status=str(args.expected_result_status or "applied"),
            source="scenario-seed",
            directive_id=directive_id,
            db_path=db_path,
        )
    )

    directive = await seed_directive(
        argparse.Namespace(
            action="RUN_REPLAY",
            target="simulation",
            target_type="swarm",
            source="overseer-seed",
            ttl_ms=300_000,
            directive_id=directive_id,
            db_path=db_path,
            payload_json=f'{{"scenario_id":"{scenario_id}","dry_run":true}}',
        )
    )

    execution = await _wait_for_execution(
        db_path=db_path,
        scenario_id=scenario_id,
        directive_id=directive_id,
        wait_seconds=float(args.wait_seconds),
        poll_interval=float(args.poll_interval),
    )

    if isinstance(execution, dict):
        evidence_records = await publish_replay_execution_evidence(
            argparse.Namespace(
                source="replay-evidence-publisher",
                db_path=db_path,
                scenario_id=scenario_id,
                directive_id=directive_id,
            )
        )

        memory_records = await publish_evidence_memory_records(
            argparse.Namespace(
                source="evidence-memory-bridge",
                db_path=db_path,
                directive_id=directive_id,
                evidence_id="",
                subject="simulation_replay_execution_check",
            )
        )
    else:
        evidence_records = []
        memory_records = []

    base_checks = _build_checks(
        scenario=scenario,
        directive=directive,
        execution=execution,
        evidence_records=evidence_records,
        memory_records=memory_records,
    )

    base_status = "passed" if all(item["status"] == "passed" for item in base_checks) else "failed"

    provisional_result_record = {
        "type": "replay_evidence_lifecycle_result",
        "scenario_id": scenario_id,
        "directive_id": directive_id,
        "status": base_status,
        "source": source,
        "checks": base_checks,
        "payload": {
            "scenario_id": scenario_id,
            "directive_id": directive_id,
            "execution_id": execution.get("execution_id") if isinstance(execution, dict) else None,
            "evidence_count": len(evidence_records),
            "memory_record_count": len(memory_records),
        },
        "created_at": time.time(),
    }

    visibility = await _collect_visibility(
        db_path=db_path,
        scenario_id=scenario_id,
        directive_id=directive_id,
        lifecycle_result=provisional_result_record,
    )

    checks = _build_checks(
        scenario=scenario,
        directive=directive,
        execution=execution,
        evidence_records=evidence_records,
        memory_records=memory_records,
        visibility=visibility,
    )

    status = "passed" if all(item["status"] == "passed" for item in checks) else "failed"

    result_record = {
        "type": "replay_evidence_lifecycle_result",
        "scenario_id": scenario_id,
        "directive_id": directive_id,
        "status": status,
        "source": source,
        "checks": checks,
        "payload": {
            "scenario_id": scenario_id,
            "directive_id": directive_id,
            "execution_id": execution.get("execution_id") if isinstance(execution, dict) else None,
            "evidence_count": len(evidence_records),
            "memory_record_count": len(memory_records),
            "visibility": visibility,
        },
        "created_at": time.time(),
    }

    await _publish_result_record(
        db_path=db_path,
        source=source,
        result_record=result_record,
    )

    return {
        "status": status,
        "scenario_id": scenario_id,
        "directive_id": directive_id,
        "scenario": scenario,
        "directive": directive,
        "execution": execution,
        "evidence_records": evidence_records,
        "memory_records": memory_records,
        "checks": checks,
        "result_record": result_record,
        "visibility": visibility,
    }


async def _wait_for_execution(
    *,
    db_path: str,
    scenario_id: str,
    directive_id: str,
    wait_seconds: float,
    poll_interval: float,
) -> dict[str, Any] | None:
    deadline = time.time() + max(0.0, wait_seconds)

    while time.time() <= deadline:
        crdt = CRDTAdapter(node_id="replay-evidence-check-reader", db_path=db_path)
        try:
            refresh = getattr(crdt, "refresh_from_storage", None)
            if callable(refresh):
                refresh()

            state = getattr(crdt, "state", {}) or {}
            for item in state.values():
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "simulation_replay_execution":
                    continue
                if str(item.get("scenario_id") or "") != scenario_id:
                    continue
                if str(item.get("directive_id") or "") != directive_id:
                    continue
                return dict(item)
        finally:
            close = getattr(crdt, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result

        await asyncio.sleep(max(0.05, poll_interval))

    return None


async def _collect_visibility(
    *,
    db_path: str,
    scenario_id: str,
    directive_id: str,
    lifecycle_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect replay lifecycle visibility from CRDT-derived summaries."""
    crdt = CRDTAdapter(node_id="replay-evidence-visibility-reader", db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        records = [item for item in state.values() if isinstance(item, dict)]

        if isinstance(lifecycle_result, dict):
            records.append(dict(lifecycle_result))

        replay_memory_records = [
            item
            for item in records
            if item.get("type") == "memory_record"
            and _record_scenario_id(item) == scenario_id
            and _record_directive_id(item) == directive_id
        ]

        lifecycle_results = [
            item
            for item in records
            if item.get("type") == "replay_evidence_lifecycle_result"
            and item.get("scenario_id") == scenario_id
            and item.get("directive_id") == directive_id
        ]

        trail_counts = _build_trail_counts(
            records=records,
            scenario_id=scenario_id,
            directive_id=directive_id,
        )

        memory_summary = build_memory_summary(replay_memory_records).to_dict()
        security_metrics = build_security_validation_heartbeat_metrics(records)

        return {
            "memory_records": len(replay_memory_records),
            "lifecycle_results": len(lifecycle_results),
            "trail_counts": trail_counts,
            "memory_summary": memory_summary,
            "security_validation": security_metrics,
        }

    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


def _build_checks(
    *,
    scenario: dict[str, Any],
    directive: dict[str, Any],
    execution: dict[str, Any] | None,
    evidence_records: list[dict[str, Any]],
    memory_records: list[dict[str, Any]],
    visibility: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    checks = [
        {
            "name": "scenario_seeded",
            "status": "passed" if scenario.get("type") == "simulation_replay_scenario" else "failed",
            "value": scenario.get("scenario_id"),
        },
        {
            "name": "directive_seeded",
            "status": "passed" if directive.get("type") == "swarm_directive" else "failed",
            "value": directive.get("directive_id"),
        },
        {
            "name": "execution_published",
            "status": "passed" if isinstance(execution, dict) else "failed",
            "value": execution.get("status") if isinstance(execution, dict) else None,
        },
        {
            "name": "execution_completed",
            "status": "passed" if isinstance(execution, dict) and execution.get("status") == "completed" else "failed",
            "value": execution.get("status") if isinstance(execution, dict) else None,
        },
        {
            "name": "evidence_published",
            "status": "passed" if evidence_records else "failed",
            "value": len(evidence_records),
        },
        {
            "name": "memory_record_published",
            "status": "passed" if memory_records else "failed",
            "value": len(memory_records),
        },
    ]

    visibility = visibility or {}
    memory_summary = visibility.get("memory_summary")
    if not isinstance(memory_summary, dict):
        memory_summary = {}

    security_validation = visibility.get("security_validation")
    if not isinstance(security_validation, dict):
        security_validation = {}

    record_type_counts = security_validation.get("security_validation_record_type_counts")
    if not isinstance(record_type_counts, dict):
        record_type_counts = {}

    trail_counts = visibility.get("trail_counts")
    if not isinstance(trail_counts, dict):
        trail_counts = {}

    checks.extend(
        [
            {
                "name": "visibility_memory_summary_replay_evidence",
                "status": (
                    "passed"
                    if int(memory_summary.get("replay_execution_evidence_records") or 0) > 0
                    else "failed"
                ),
                "value": memory_summary.get("replay_execution_evidence_records"),
            },
            {
                "name": "visibility_security_lifecycle_validation",
                "status": (
                    "passed"
                    if int(record_type_counts.get("replay_evidence_lifecycle_result") or 0) > 0
                    else "failed"
                ),
                "value": record_type_counts.get("replay_evidence_lifecycle_result"),
            },
            {
                "name": "visibility_crdt_trail_complete",
                "status": (
                    "passed"
                    if all(
                        int(trail_counts.get(name) or 0) > 0
                        for name in (
                            "simulation_replay_scenario",
                            "swarm_directive",
                            "simulation_replay_execution",
                            "evidence_record",
                            "memory_record",
                            "replay_evidence_lifecycle_result",
                        )
                    )
                    else "failed"
                ),
                "value": dict(trail_counts),
            },
        ]
    )

    return checks

def _record_payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _record_scenario_id(record: Mapping[str, Any]) -> str:
    payload = _record_payload(record)
    return str(record.get("scenario_id") or payload.get("scenario_id") or "").strip()

def _build_trail_counts(
    *,
    records: list[dict[str, Any]],
    scenario_id: str,
    directive_id: str,
) -> dict[str, int]:
    """Count replay lifecycle CRDT trail records for the target scenario/directive."""
    counts = {
        "simulation_replay_scenario": 0,
        "swarm_directive": 0,
        "simulation_replay_execution": 0,
        "evidence_record": 0,
        "memory_record": 0,
        "replay_evidence_lifecycle_result": 0,
    }

    for record in records:
        if not isinstance(record, dict):
            continue

        record_type = str(record.get("type") or "").strip()
        if record_type not in counts:
            continue

        if record_type == "simulation_replay_scenario":
            if _record_scenario_id(record) == scenario_id:
                counts[record_type] += 1
            continue

        if record_type in {
            "swarm_directive",
            "simulation_replay_execution",
            "evidence_record",
            "memory_record",
            "replay_evidence_lifecycle_result",
        }:
            if _record_directive_id(record) == directive_id:
                counts[record_type] += 1

    return counts


def _record_directive_id(record: Mapping[str, Any]) -> str:
    payload = _record_payload(record)
    return str(record.get("directive_id") or payload.get("directive_id") or "").strip()


async def _publish_result_record(
    *,
    db_path: str,
    source: str,
    result_record: dict[str, Any],
) -> None:
    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    try:
        await crdt.add_genome(result_record)
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


async def async_main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    result = await run_replay_evidence_check(args)

    logger.info(
        "Replay evidence lifecycle check: status=%s scenario_id=%s directive_id=%s",
        result["status"],
        result["scenario_id"],
        result["directive_id"],
    )

    for check in result["checks"]:
        logger.info(
            "Replay evidence check: name=%s status=%s value=%s",
            check["name"],
            check["status"],
            check.get("value"),
        )

    return 0 if result["status"] == "passed" else 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()