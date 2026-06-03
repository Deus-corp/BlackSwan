"""Dry-run runner for replay lifecycle retry execution plans.

This helper is intentionally non-executing until execution_enabled=True is
supported by a future controlled runner.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run replay lifecycle retry execution plans.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="retry-plan-runner",
        help="Source node id for result records.",
    )
    parser.add_argument(
        "--plan-id",
        default="",
        help="Optional plan_id filter.",
    )
    return parser


async def run_retry_execution_plans(args: argparse.Namespace) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "retry-plan-runner")
    plan_id_filter = str(getattr(args, "plan_id", "") or "").strip()

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        plans = [
            item
            for item in state.values()
            if isinstance(item, Mapping)
            and item.get("type") == "replay_lifecycle_retry_execution_plan"
            and (not plan_id_filter or item.get("plan_id") == plan_id_filter)
        ]

        existing_result_plan_ids = {
            str(item.get("plan_id") or "")
            for item in state.values()
            if isinstance(item, Mapping)
            and item.get("type") == "replay_lifecycle_retry_execution_result"
        }

        results: list[dict[str, Any]] = []

        for plan in plans:
            plan_id = str(plan.get("plan_id") or "").strip()
            if not plan_id or plan_id in existing_result_plan_ids:
                continue

            result = build_retry_execution_result(
                plan,
                source=source,
            )
            await crdt.add_genome(result)
            existing_result_plan_ids.add(plan_id)
            results.append(result)

            logger.info(
                "Published retry execution result: plan_id=%s status=%s reason=%s",
                result.get("plan_id"),
                result.get("status"),
                result.get("reason"),
            )

        return results
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def build_retry_execution_result(
    plan: Mapping[str, Any],
    *,
    source: str = "retry-plan-runner",
) -> dict[str, Any]:
    """Build non-executing result for a retry execution plan."""
    if not isinstance(plan, Mapping):
        raise TypeError("plan must be a mapping")

    if plan.get("type") != "replay_lifecycle_retry_execution_plan":
        raise ValueError("plan must have type='replay_lifecycle_retry_execution_plan'")

    plan_id = str(plan.get("plan_id") or "").strip()
    if not plan_id:
        raise ValueError("plan_id must be present")

    execution_enabled = bool(plan.get("execution_enabled"))
    status = "skipped"
    reason = "execution_disabled"

    if execution_enabled:
        status = "rejected"
        reason = "execution_not_supported"

    return {
        "type": "replay_lifecycle_retry_execution_result",
        "result_id": f"replay-retry-result-{plan_id}",
        "plan_id": plan_id,
        "proposal_id": plan.get("proposal_id"),
        "approval_id": plan.get("approval_id"),
        "status": status,
        "reason": reason,
        "source": str(source or "retry-plan-runner"),
        "execution_enabled": execution_enabled,
        "payload": {
            "plan_id": plan_id,
            "proposal_id": plan.get("proposal_id"),
            "approval_id": plan.get("approval_id"),
            "timeout_profile": plan.get("timeout_profile"),
            "decision_mode": plan.get("decision_mode"),
            "command_template": plan.get("command_template"),
            "execution_enabled": execution_enabled,
            "executed": False,
        },
        "created_at": time.time(),
    }


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    results = await run_retry_execution_plans(args)

    logger.info("Retry execution plan runner completed: results=%d", len(results))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()