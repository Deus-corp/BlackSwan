"""Build execution eligibility records for rendered retry commands.

This helper does not execute commands. It only records whether a rendered retry
command is eligible for a future controlled runner.
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


SAFE_BLOCK_REASONS = {
    "execution_disabled",
    "execution_not_supported",
    "missing_rendered_command_result",
    "missing_rendered_command",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build non-executing retry execution eligibility records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="retry-execution-eligibility",
        help="Source node id for published eligibility records.",
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


async def build_retry_execution_eligibilities(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Build and publish execution eligibility records for rendered commands."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "retry-execution-eligibility")
    rendered_command_id = str(getattr(args, "rendered_command_id", "") or "").strip()
    plan_id = str(getattr(args, "plan_id", "") or "").strip()

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

        eligibilities: list[dict[str, Any]] = []
        for rendered_command in rendered_commands:
            current_rendered_command_id = str(
                rendered_command.get("rendered_command_id") or ""
            ).strip()
            current_plan_id = str(rendered_command.get("plan_id") or "").strip()

            existing_eligibility = _find_existing_eligibility(
                records,
                rendered_command_id=current_rendered_command_id,
                plan_id=current_plan_id,
            )
            if existing_eligibility is not None:
                logger.info(
                    "Skipping duplicate retry execution eligibility: rendered_command_id=%s plan_id=%s",
                    current_rendered_command_id,
                    current_plan_id,
                )
                continue

            result = _find_rendered_command_result(
                records,
                rendered_command_id=current_rendered_command_id,
                plan_id=current_plan_id,
            )
            eligibility = build_retry_execution_eligibility(
                rendered_command,
                rendered_command_result=result,
                source=source,
            )
            await crdt.add_genome(eligibility)
            records.append(eligibility)
            eligibilities.append(eligibility)
            logger.info(
                "Published retry execution eligibility: rendered_command_id=%s status=%s reason=%s",
                eligibility.get("rendered_command_id"),
                eligibility.get("status"),
                eligibility.get("reason"),
            )

        logger.info("Retry execution eligibility builder completed: records=%d", len(eligibilities))
        return eligibilities
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def build_retry_execution_eligibility(
    rendered_command: Mapping[str, Any] | None,
    *,
    rendered_command_result: Mapping[str, Any] | None = None,
    source: str = "retry-execution-eligibility",
) -> dict[str, Any]:
    """Build a non-executing eligibility record."""
    if rendered_command is None:
        return _blocked_eligibility(
            rendered_command_id="",
            plan_id="",
            proposal_id="",
            approval_id="",
            timeout_profile="unknown",
            decision_mode="unknown",
            command="",
            reason="missing_rendered_command",
            source=source,
        )

    if rendered_command.get("type") != "replay_lifecycle_retry_rendered_command":
        raise ValueError("rendered_command must have type='replay_lifecycle_retry_rendered_command'")

    rendered_command_id = str(rendered_command.get("rendered_command_id") or "").strip()
    plan_id = str(rendered_command.get("plan_id") or "").strip()
    proposal_id = str(rendered_command.get("proposal_id") or "").strip()
    approval_id = str(rendered_command.get("approval_id") or "").strip()
    timeout_profile = str(rendered_command.get("timeout_profile") or "unknown").strip() or "unknown"
    decision_mode = str(rendered_command.get("decision_mode") or "unknown").strip() or "unknown"
    command = str(rendered_command.get("command") or "").strip()
    execution_enabled = bool(rendered_command.get("execution_enabled"))

    if not rendered_command_id:
        raise ValueError("rendered_command_id must be present")
    if not plan_id:
        raise ValueError("plan_id must be present")
    if not command:
        raise ValueError("command must be present")

    if rendered_command_result is None:
        return _blocked_eligibility(
            rendered_command_id=rendered_command_id,
            plan_id=plan_id,
            proposal_id=proposal_id,
            approval_id=approval_id,
            timeout_profile=timeout_profile,
            decision_mode=decision_mode,
            command=command,
            reason="missing_rendered_command_result",
            source=source,
        )

    result_status = str(rendered_command_result.get("status") or "").strip().lower()
    result_reason = str(rendered_command_result.get("reason") or "").strip()
    result_executed = bool(
        (rendered_command_result.get("payload") or {}).get("executed")
        if isinstance(rendered_command_result.get("payload"), Mapping)
        else False
    )

    if result_executed:
        reason = "execution_not_supported"
    elif not execution_enabled:
        reason = "execution_disabled"
    elif result_status == "rejected" and result_reason == "execution_not_supported":
        reason = "execution_not_supported"
    else:
        reason = "execution_not_supported"

    return _blocked_eligibility(
        rendered_command_id=rendered_command_id,
        plan_id=plan_id,
        proposal_id=proposal_id,
        approval_id=approval_id,
        timeout_profile=timeout_profile,
        decision_mode=decision_mode,
        command=command,
        reason=reason,
        source=source,
    )


def _blocked_eligibility(
    *,
    rendered_command_id: str,
    plan_id: str,
    proposal_id: str,
    approval_id: str,
    timeout_profile: str,
    decision_mode: str,
    command: str,
    reason: str,
    source: str,
) -> dict[str, Any]:
    if reason not in SAFE_BLOCK_REASONS:
        raise ValueError(f"unsupported eligibility reason: {reason}")

    eligibility_id = _eligibility_id(
        rendered_command_id=rendered_command_id,
        plan_id=plan_id,
        reason=reason,
    )

    return {
        "type": "replay_lifecycle_retry_execution_eligibility",
        "eligibility_id": eligibility_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": "blocked",
        "reason": reason,
        "source": str(source or "retry-execution-eligibility"),
        "execution_supported": False,
        "execution_enabled": False,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "payload": {
            "rendered_command_id": rendered_command_id,
            "plan_id": plan_id,
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "status": "blocked",
            "reason": reason,
            "execution_supported": False,
            "execution_enabled": False,
            "executed": False,
            "timeout_profile": timeout_profile,
            "decision_mode": decision_mode,
            "command": command,
        },
        "created_at": time.time(),
    }


def _find_rendered_command_result(
    records: list[Mapping[str, Any]],
    *,
    rendered_command_id: str,
    plan_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != "replay_lifecycle_retry_rendered_command_result":
            continue
        if rendered_command_id and str(item.get("rendered_command_id") or "").strip() == rendered_command_id:
            return item
        if plan_id and str(item.get("plan_id") or "").strip() == plan_id:
            return item
    return None

def _find_existing_eligibility(
    records: list[Mapping[str, Any]],
    *,
    rendered_command_id: str,
    plan_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != "replay_lifecycle_retry_execution_eligibility":
            continue
        if (
            rendered_command_id
            and str(item.get("rendered_command_id") or "").strip() == rendered_command_id
        ):
            return item
        if plan_id and str(item.get("plan_id") or "").strip() == plan_id:
            return item
    return None

def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    plan_id: str,
) -> bool:
    if rendered_command_id and str(record.get("rendered_command_id") or "").strip() != rendered_command_id:
        return False
    if plan_id and str(record.get("plan_id") or "").strip() != plan_id:
        return False
    return True


def _eligibility_id(
    *,
    rendered_command_id: str,
    plan_id: str,
    reason: str,
) -> str:
    digest = hashlib.sha256(
        "|".join([rendered_command_id, plan_id, reason]).encode("utf-8")
    ).hexdigest()[:16]
    return f"replay-retry-eligibility-{digest}"


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    await build_retry_execution_eligibilities(args)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()