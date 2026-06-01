"""Publish evidence records from simulation replay execution records."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish replay execution evidence into CRDT.")
    parser.add_argument("--source", default="replay-evidence-publisher", help="Evidence source.")
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    parser.add_argument("--scenario-id", default="", help="Optional scenario id filter.")
    parser.add_argument("--directive-id", default="", help="Optional directive id filter.")
    return parser


async def publish_replay_execution_evidence(args: argparse.Namespace) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "replay-evidence-publisher")
    scenario_id = str(getattr(args, "scenario_id", "") or "").strip()
    directive_id = str(getattr(args, "directive_id", "") or "").strip()

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        executions = [
            item
            for item in state.values()
            if isinstance(item, dict)
            and item.get("type") == "simulation_replay_execution"
            and (not scenario_id or str(item.get("scenario_id") or "") == scenario_id)
            and (not directive_id or str(item.get("directive_id") or "") == directive_id)
        ]

        evidence_records = [_build_evidence_record(item, source=source) for item in executions]

        for evidence in evidence_records:
            await crdt.add_genome(evidence)

        return evidence_records

    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


def _build_evidence_record(execution: dict[str, Any], *, source: str) -> dict[str, Any]:
    status = str(execution.get("status") or "").strip().lower()
    passed = status == "completed"

    scenario_id = str(execution.get("scenario_id") or "").strip()
    directive_id = str(execution.get("directive_id") or "").strip()
    execution_id = str(execution.get("execution_id") or f"exec-{scenario_id}").strip()

    checks = [
        {
            "name": "replay_execution_present",
            "status": "passed",
            "value": True,
        },
        {
            "name": "replay_execution_completed",
            "status": "passed" if passed else "failed",
            "value": status,
        },
        {
            "name": "dry_run",
            "status": "passed" if bool(execution.get("dry_run")) else "failed",
            "value": bool(execution.get("dry_run")),
        },
    ]

    return {
        "type": "evidence_record",
        "evidence_id": f"evidence-{execution_id}",
        "subject": "simulation_replay_execution_check",
        "status": "passed" if passed else "failed",
        "confidence": 1.0 if passed else 0.0,
        "source": source,
        "scenario_id": scenario_id,
        "directive_id": directive_id,
        "execution_id": execution_id,
        "payload": {
            "scenario_id": scenario_id,
            "directive_id": directive_id,
            "execution_id": execution_id,
            "execution": dict(execution),
            "checks": checks,
        },
        "created_at": time.time(),
    }


async def async_main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    evidence_records = await publish_replay_execution_evidence(args)

    logger.info(
        "Published replay execution evidence: count=%d scenario_id=%s directive_id=%s db=%s",
        len(evidence_records),
        args.scenario_id or "*",
        args.directive_id or "*",
        args.db_path or config.crdt_db_path,
    )

    for evidence in evidence_records:
        logger.info(
            "Replay evidence: evidence_id=%s status=%s scenario_id=%s directive_id=%s",
            evidence.get("evidence_id"),
            evidence.get("status"),
            evidence.get("scenario_id"),
            evidence.get("directive_id"),
        )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()