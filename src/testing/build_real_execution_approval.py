"""Build explicit real execution approval records.

This module records explicit approval intent for future real execution, but it
never enables real execution and never invokes subprocesses.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

REAL_APPROVAL_TYPE = "replay_lifecycle_retry_real_execution_approval"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_approval_record(
    real_preflight: Mapping[str, Any],
    *,
    approval_status: str = "pending",
    source: str = "real-execution-approval",
) -> dict[str, Any]:
    """Build a fail-closed explicit real execution approval record."""
    real_execution_preflight_id = _clean(
        real_preflight.get("real_execution_preflight_id")
    )
    controlled_execution_result_id = _clean(
        real_preflight.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(real_preflight.get("rendered_command_id"))
    plan_id = _clean(real_preflight.get("plan_id"))
    proposal_id = _clean(real_preflight.get("proposal_id"))
    approval_id = _clean(real_preflight.get("approval_id"))
    timeout_profile = _clean(real_preflight.get("timeout_profile")) or "standard"
    decision_mode = _clean(real_preflight.get("decision_mode")) or "manual"
    command = _clean(real_preflight.get("command"))

    approval_status = _clean(approval_status).lower() or "pending"
    if approval_status not in {"pending", "approved", "rejected"}:
        raise ValueError("approval_status must be pending, approved, or rejected")

    if not real_execution_preflight_id:
        raise ValueError("real_execution_preflight_id is required")
    if not controlled_execution_result_id:
        raise ValueError("controlled_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    operator_authorized = bool(real_preflight.get("operator_authorized"))
    real_execution_requested = bool(real_preflight.get("real_execution_requested"))

    real_execution_approval_id = _stable_id(
        "replay-retry-real-approval",
        real_execution_preflight_id,
        controlled_execution_result_id,
        approval_status,
    )

    reason = (
        "real_execution_explicit_approval_rejected"
        if approval_status == "rejected"
        else "real_execution_explicit_approval_required"
    )

    payload = {
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "reason": reason,
        "operator_authorized": operator_authorized,
        "real_execution_requested": real_execution_requested,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
    }

    return {
        "type": REAL_APPROVAL_TYPE,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "approval_status": approval_status,
        "reason": reason,
        "operator_authorized": operator_authorized,
        "real_execution_requested": real_execution_requested,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    real_execution_preflight_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_preflight_id
        and _clean(record.get("real_execution_preflight_id"))
        != real_execution_preflight_id
    ):
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    return True


def _find_existing_approval(
    records: list[Mapping[str, Any]],
    *,
    real_execution_preflight_id: str,
    controlled_execution_result_id: str,
    approval_status: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_APPROVAL_TYPE:
            continue
        if (
            _clean(item.get("real_execution_preflight_id"))
            == real_execution_preflight_id
            and _clean(item.get("controlled_execution_result_id"))
            == controlled_execution_result_id
            and _clean(item.get("approval_status")).lower() == approval_status
        ):
            return item
    return None


async def build_real_execution_approvals(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish explicit real execution approval records from preflights."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-approval"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    real_execution_preflight_id = _clean(
        getattr(args, "real_execution_preflight_id", "")
    )
    approval_status = _clean(getattr(args, "approval_status", "")) or "pending"
    approval_status = approval_status.lower()

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    preflights = [
        item
        for item in records
        if item.get("type") == "replay_lifecycle_retry_real_execution_preflight"
        and _matches_filters(
            item,
            real_execution_preflight_id=real_execution_preflight_id,
            rendered_command_id=rendered_command_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for preflight in preflights:
        current_preflight_id = _clean(preflight.get("real_execution_preflight_id"))
        current_controlled_result_id = _clean(
            preflight.get("controlled_execution_result_id")
        )

        if _find_existing_approval(
            records,
            real_execution_preflight_id=current_preflight_id,
            controlled_execution_result_id=current_controlled_result_id,
            approval_status=approval_status,
        ):
            logger.info(
                "Skipping duplicate real execution approval: real_execution_preflight_id=%s status=%s",
                current_preflight_id,
                approval_status,
            )
            continue

        record = build_real_execution_approval_record(
            preflight,
            approval_status=approval_status,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution approval: real_execution_approval_id=%s status=%s real_execution_enabled=%s subprocess_enabled=%s",
            record.get("real_execution_approval_id"),
            record.get("approval_status"),
            record.get("real_execution_enabled"),
            record.get("subprocess_enabled"),
        )

    logger.info("Real execution approval builder completed: approvals=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build explicit fail-closed real execution approval records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Rendered command id filter.",
    )
    parser.add_argument(
        "--real-execution-preflight-id",
        default="",
        help="Real execution preflight id filter.",
    )
    parser.add_argument(
        "--approval-status",
        default="pending",
        choices=("pending", "approved", "rejected"),
        help="Approval status to record. Real execution remains disabled for all statuses.",
    )
    parser.add_argument(
        "--source",
        default="real-execution-approval",
        help="CRDT source/node id.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON records.")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_approvals(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Real execution approval builder completed: approvals={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()