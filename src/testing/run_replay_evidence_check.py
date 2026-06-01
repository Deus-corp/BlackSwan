"""Run the controlled replay evidence lifecycle check end-to-end."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter
from src.testing.evidence_memory_bridge import publish_evidence_memory_records
from src.testing.publish_replay_execution_evidence import publish_replay_execution_evidence
from src.testing.seed_directive import seed_directive
from src.testing.seed_replay_scenario import seed_replay_scenario

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

    checks = _build_checks(
        scenario=scenario,
        directive=directive,
        execution=execution,
        evidence_records=evidence_records,
        memory_records=memory_records,
    )

    status = "passed" if all(item["status"] == "passed" for item in checks) else "failed"

    result_record = {
        "type": "replay_evidence_lifecycle_result",
        "scenario_id": scenario_id,
        "directive_id": directive_id,
        "status": status,
        "source": str(args.source or "replay-evidence-check"),
        "checks": checks,
        "payload": {
            "scenario_id": scenario_id,
            "directive_id": directive_id,
            "execution_id": execution.get("execution_id") if isinstance(execution, dict) else None,
            "evidence_count": len(evidence_records),
            "memory_record_count": len(memory_records),
        },
        "created_at": time.time(),
    }

    await _publish_result_record(
        db_path=db_path,
        source=str(args.source or "replay-evidence-check"),
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


def _build_checks(
    *,
    scenario: dict[str, Any],
    directive: dict[str, Any],
    execution: dict[str, Any] | None,
    evidence_records: list[dict[str, Any]],
    memory_records: list[dict[str, Any]],
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

    return checks


async def async_main() -> None:
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


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()