"""Publish simulation replay scenarios from runtime evidence memory records."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.simulation.replay import build_replay_scenarios_from_memory_records

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish simulation replay scenarios into CRDT.")
    parser.add_argument("--source", default="simulation-replay-builder", help="Scenario source.")
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    parser.add_argument(
        "--directive-id",
        default="",
        help="Optional directive id filter for runtime evidence memory records.",
    )
    return parser


async def publish_replay_scenarios(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Build replay scenarios from CRDT memory records and publish them into CRDT."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "simulation-replay-builder")
    directive_id = str(getattr(args, "directive_id", "") or "").strip()

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        records = [
            item
            for item in state.values()
            if isinstance(item, dict)
            and item.get("type") == "memory_record"
            and item.get("kind") == "runtime_evidence"
            and (not directive_id or _directive_id(item) == directive_id)
        ]

        logger.info(
            "Found runtime evidence memory records: count=%d directive_id=%s",
            len(records),
            directive_id or "*",
        )

        scenarios = build_replay_scenarios_from_memory_records(records, source=source)

        for scenario in scenarios:
            await crdt.add_genome(scenario)

        return scenarios

    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


async def async_main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    scenarios = await publish_replay_scenarios(args)

    logger.info(
        "Published replay scenarios: count=%d directive_id=%s db=%s",
        len(scenarios),
        args.directive_id or "*",
        args.db_path or config.crdt_db_path,
    )

    for scenario in scenarios:
        logger.info(
            "Replay scenario: scenario_id=%s action=%s directive_id=%s status=%s",
            scenario.get("scenario_id"),
            scenario.get("action"),
            scenario.get("directive_id"),
            scenario.get("status"),
        )

    if not scenarios:
        logger.warning(
            "No replay scenarios were published. Ensure CRDT contains passed "
            "memory_record kind=runtime_evidence for directive_id=%s.",
            args.directive_id or "*",
        )


def main() -> None:
    asyncio.run(async_main())


def _directive_id(record: dict[str, Any]) -> str:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return str(payload.get("directive_id") or record.get("directive_id") or "").strip()


if __name__ == "__main__":
    main()