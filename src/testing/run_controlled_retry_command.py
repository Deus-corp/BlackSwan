"""Reject-only skeleton for future controlled retry command execution.

This helper intentionally does not execute rendered retry commands. It publishes
a controlled execution result record so validation and observability can be
implemented before any controlled execution path exists.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from hashlib import sha256
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)


CONTROLLED_RESULT_TYPE = "replay_lifecycle_retry_controlled_execution_result"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_suffix(*parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    plan_id: str,
) -> bool:
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if plan_id and _clean(record.get("plan_id")) != plan_id:
        return False
    return True


def _find_existing_controlled_result(
    records: list[Mapping[str, Any]],
    *,
    rendered_command_id: str,
    plan_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != CONTROLLED_RESULT_TYPE:
            continue
        if rendered_command_id and _clean(item.get("rendered_command_id")) == rendered_command_id:
            return item
        if plan_id and _clean(item.get("plan_id")) == plan_id:
            return item
    return None


def build_controlled_retry_command_result(
    rendered_command: Mapping[str, Any],
    *,
    source: str = "controlled-retry-command-runner",
) -> dict[str, Any]:
    """Build a reject-only controlled execution result for a rendered command."""
    rendered_command_id = _clean(rendered_command.get("rendered_command_id"))
    if not rendered_command_id:
        raise ValueError("rendered_command_id must be present")

    plan_id = _clean(rendered_command.get("plan_id"))
    proposal_id = _clean(rendered_command.get("proposal_id"))
    approval_id = _clean(rendered_command.get("approval_id"))
    command = _clean(rendered_command.get("command"))
    timeout_profile = _clean(rendered_command.get("timeout_profile")) or "unknown"
    decision_mode = _clean(rendered_command.get("decision_mode")) or "unknown"
    execution_enabled = bool(rendered_command.get("execution_enabled"))

    result_id = (
        "replay-retry-controlled-result-"
        + _stable_suffix(rendered_command_id, plan_id, command)
    )

    return {
        "type": CONTROLLED_RESULT_TYPE,
        "controlled_execution_result_id": result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "source": source,
        "execution_enabled": execution_enabled,
        "operator_authorized": False,
        "allowlist_matched": False,
        "readiness_score": 0,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "payload": {
            "rendered_command_id": rendered_command_id,
            "plan_id": plan_id,
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "status": "rejected",
            "reason": "controlled_execution_not_implemented",
            "execution_enabled": execution_enabled,
            "operator_authorized": False,
            "allowlist_matched": False,
            "readiness_score": 0,
            "timeout_profile": timeout_profile,
            "decision_mode": decision_mode,
            "command": command,
            "executed": False,
        },
    }


async def run_controlled_retry_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Publish reject-only controlled execution result records."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(getattr(args, "source", "") or "controlled-retry-command-runner")
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    plan_id = _clean(getattr(args, "plan_id", ""))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        records = [item for item in state.values() if isinstance(item, Mapping)]

        rendered_commands = [
            item
            for item in records
            if item.get("type") == "replay_lifecycle_retry_rendered_command"
            and _matches_filters(
                item,
                rendered_command_id=rendered_command_id,
                plan_id=plan_id,
            )
        ]

        results: list[dict[str, Any]] = []
        for rendered_command in rendered_commands:
            current_rendered_command_id = _clean(rendered_command.get("rendered_command_id"))
            current_plan_id = _clean(rendered_command.get("plan_id"))

            existing = _find_existing_controlled_result(
                records,
                rendered_command_id=current_rendered_command_id,
                plan_id=current_plan_id,
            )
            if existing is not None:
                logger.info(
                    "Skipping duplicate controlled retry command result: rendered_command_id=%s plan_id=%s",
                    current_rendered_command_id,
                    current_plan_id,
                )
                continue

            result = build_controlled_retry_command_result(
                rendered_command,
                source=source,
            )
            await crdt.add_genome(result)
            records.append(result)
            results.append(result)
            logger.info(
                "Published controlled retry command result: rendered_command_id=%s status=%s reason=%s",
                result.get("rendered_command_id"),
                result.get("status"),
                result.get("reason"),
            )

        logger.info("Controlled retry command runner completed: results=%d", len(results))
        return results
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish reject-only controlled retry command result records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="controlled-retry-command-runner",
        help="Source node id for published records.",
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result.",
    )
    return parser


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    results = await run_controlled_retry_commands(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Controlled retry command runner completed: results={len(results)}")

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()