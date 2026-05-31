"""Seed a simulation replay scenario into the runtime CRDT ledger."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter

logger = logging.getLogger(__name__)

SAFE_REPLAY_ACTIONS = {
    "OBSERVE",
    "REDUCE_RISK",
    "SET_DRY_RUN",
    "PROMOTE_GOLD_CANDIDATES",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed a simulation replay scenario into CRDT.")
    parser.add_argument(
        "--scenario-id",
        default="replay-runtime-reduce-risk-1",
        help="Replay scenario id.",
    )
    parser.add_argument("--action", default="REDUCE_RISK", help="Replay action.")
    parser.add_argument(
        "--expected-result-status",
        default="applied",
        help="Expected original directive result status.",
    )
    parser.add_argument(
        "--source",
        default="scenario-seed",
        help="Scenario source node id.",
    )
    parser.add_argument(
        "--directive-id",
        default="runtime-reduce-risk-1",
        help="Original directive id represented by this replay scenario.",
    )
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    return parser


async def seed_replay_scenario(args: argparse.Namespace) -> dict[str, Any]:
    action = str(args.action or "").strip().upper()
    if action not in SAFE_REPLAY_ACTIONS:
        raise ValueError(f"Unsafe replay action: {action}. Allowed: {sorted(SAFE_REPLAY_ACTIONS)}")

    scenario_id = str(args.scenario_id or "").strip()
    if not scenario_id:
        raise ValueError("scenario-id is required")

    expected_result_status = str(args.expected_result_status or "applied").strip().lower()
    if not expected_result_status:
        raise ValueError("expected-result-status is required")

    source = str(args.source or "scenario-seed")
    db_path = str(args.db_path or config.crdt_db_path)

    scenario = {
        "type": "simulation_replay_scenario",
        "scenario_id": scenario_id,
        "status": "pending",
        "replay_kind": "manual_seed",
        "directive_id": str(args.directive_id or ""),
        "action": action,
        "expected_result_status": expected_result_status,
        "source": source,
        "payload": {
            "seeded": True,
            "runtime_check": True,
        },
        "created_at": time.time(),
    }

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        await crdt.add_genome(scenario)
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result

    return scenario


async def async_main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    scenario = await seed_replay_scenario(args)

    logger.info(
        "Seeded replay scenario: scenario_id=%s action=%s expected_result_status=%s db=%s",
        scenario["scenario_id"],
        scenario["action"],
        scenario["expected_result_status"],
        args.db_path or config.crdt_db_path,
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()