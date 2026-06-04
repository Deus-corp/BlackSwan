"""Dry-run rendered replay retry commands.

This helper reads `replay_lifecycle_retry_rendered_command` records and publishes
non-executing `replay_lifecycle_retry_rendered_command_result` records. It never
executes command text.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import time
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run rendered replay retry commands without executing them.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="rendered-retry-command-runner",
        help="Source node id for published result records.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Optional rendered command id filter.",
    )
    parser.add_argument(
        "--plan-id",
        default="",
        help="Optional plan id filter.",
    )
    return parser


async def run_rendered_retry_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Publish dry-run results for rendered retry commands."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "rendered-retry-command-runner")
    rendered_command_id = str(getattr(args, "rendered_command_id", "") or "").strip()
    plan_id = str(getattr(args, "plan_id", "") or "").strip()

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        rendered_commands = [
            item
            for item in state.values()
            if isinstance(item, Mapping)
            and item.get("type") == "replay_lifecycle_retry_rendered_command"
            and _matches_filters(
                item,
                rendered_command_id=rendered_command_id,
                plan_id=plan_id,
            )
        ]

        results: list[dict[str, Any]] = []
        for rendered_command in rendered_commands:
            result = build_rendered_retry_command_result(
                rendered_command,
                source=source,
            )
            await crdt.add_genome(result)
            results.append(result)
            logger.info(
                "Published rendered retry command result: rendered_command_id=%s status=%s reason=%s",
                result.get("rendered_command_id"),
                result.get("status"),
                result.get("reason"),
            )

        logger.info("Rendered retry command runner completed: results=%d", len(results))
        return results
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def build_rendered_retry_command_result(
    rendered_command: Mapping[str, Any],
    *,
    source: str = "rendered-retry-command-runner",
) -> dict[str, Any]:
    """Build a non-executing result for a rendered retry command."""
    if not isinstance(rendered_command, Mapping):
        raise TypeError("rendered_command must be a mapping")

    if rendered_command.get("type") != "replay_lifecycle_retry_rendered_command":
        raise ValueError("rendered_command must have type='replay_lifecycle_retry_rendered_command'")

    rendered_command_id = str(rendered_command.get("rendered_command_id") or "").strip()
    plan_id = str(rendered_command.get("plan_id") or "").strip()
    proposal_id = str(rendered_command.get("proposal_id") or "").strip()
    approval_id = str(rendered_command.get("approval_id") or "").strip()
    timeout_profile = str(rendered_command.get("timeout_profile") or "").strip()
    decision_mode = str(rendered_command.get("decision_mode") or "").strip()
    command = str(rendered_command.get("command") or "").strip()
    execution_enabled = bool(rendered_command.get("execution_enabled"))

    if not rendered_command_id:
        raise ValueError("rendered_command_id must be present")
    if not plan_id:
        raise ValueError("plan_id must be present")
    if not command:
        raise ValueError("command must be present")

    status = "rejected" if execution_enabled else "skipped"
    reason = "execution_not_supported" if execution_enabled else "execution_disabled"

    result_id = _result_id(
        rendered_command_id=rendered_command_id,
        plan_id=plan_id,
        status=status,
        reason=reason,
    )

    return {
        "type": "replay_lifecycle_retry_rendered_command_result",
        "rendered_command_result_id": result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": status,
        "reason": reason,
        "source": str(source or "rendered-retry-command-runner"),
        "execution_enabled": execution_enabled,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "payload": {
            "rendered_command_id": rendered_command_id,
            "plan_id": plan_id,
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "timeout_profile": timeout_profile,
            "decision_mode": decision_mode,
            "command": command,
            "execution_enabled": execution_enabled,
            "executed": False,
        },
        "created_at": time.time(),
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    plan_id: str,
) -> bool:
    if rendered_command_id and str(record.get("rendered_command_id") or "").strip() != rendered_command_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("rendered_command_id") or "").strip() != rendered_command_id:
            return False

    if plan_id and str(record.get("plan_id") or "").strip() != plan_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("plan_id") or "").strip() != plan_id:
            return False

    return True


def _result_id(
    *,
    rendered_command_id: str,
    plan_id: str,
    status: str,
    reason: str,
) -> str:
    digest = hashlib.sha256(
        "|".join([rendered_command_id, plan_id, status, reason]).encode("utf-8")
    ).hexdigest()[:16]
    return f"replay-retry-rendered-result-{digest}"


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    await run_rendered_retry_commands(args)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()