"""Build immutable real execution approval transition records.

Approval records are immutable. This module records status transitions without
enabling real execution and without invoking subprocesses.
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

REAL_APPROVAL_TRANSITION_TYPE = (
    "replay_lifecycle_retry_real_execution_approval_transition"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_approval_transition_record(
    real_approval: Mapping[str, Any],
    *,
    to_status: str,
    source: str = "real-execution-approval-transition",
) -> dict[str, Any]:
    """Build a fail-closed immutable approval transition record."""
    real_execution_approval_id = _clean(
        real_approval.get("real_execution_approval_id")
    )
    real_execution_preflight_id = _clean(
        real_approval.get("real_execution_preflight_id")
    )
    controlled_execution_result_id = _clean(
        real_approval.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(real_approval.get("rendered_command_id"))
    plan_id = _clean(real_approval.get("plan_id"))
    proposal_id = _clean(real_approval.get("proposal_id"))
    approval_id = _clean(real_approval.get("approval_id"))
    from_status = _clean(real_approval.get("approval_status")).lower() or "pending"
    to_status = _clean(to_status).lower()
    timeout_profile = _clean(real_approval.get("timeout_profile")) or "standard"
    decision_mode = _clean(real_approval.get("decision_mode")) or "manual"
    command = _clean(real_approval.get("command"))

    if not real_execution_approval_id:
        raise ValueError("real_execution_approval_id is required")
    if not real_execution_preflight_id:
        raise ValueError("real_execution_preflight_id is required")
    if not controlled_execution_result_id:
        raise ValueError("controlled_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")
    if from_status not in {"pending", "approved", "rejected"}:
        raise ValueError("from_status must be pending, approved, or rejected")
    if to_status not in {"approved", "rejected"}:
        raise ValueError("to_status must be approved or rejected")
    if from_status != "pending":
        raise ValueError("only pending approvals may transition")
    if from_status == to_status:
        raise ValueError("transition must change status")

    transition_id = _stable_id(
        "replay-retry-real-approval-transition",
        real_execution_approval_id,
        real_execution_preflight_id,
        from_status,
        to_status,
    )

    payload = {
        "real_execution_approval_transition_id": transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "from_status": from_status,
        "to_status": to_status,
        "reason": "real_execution_approval_transition_recorded",
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
    }

    return {
        "type": REAL_APPROVAL_TRANSITION_TYPE,
        "real_execution_approval_transition_id": transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "from_status": from_status,
        "to_status": to_status,
        "reason": "real_execution_approval_transition_recorded",
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
    real_execution_approval_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_approval_id
        and _clean(record.get("real_execution_approval_id"))
        != real_execution_approval_id
    ):
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    return True


def _find_existing_transition(
    records: list[Mapping[str, Any]],
    *,
    real_execution_approval_id: str,
    to_status: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_APPROVAL_TRANSITION_TYPE:
            continue
        if (
            _clean(item.get("real_execution_approval_id"))
            == real_execution_approval_id
            and _clean(item.get("to_status")).lower() == to_status
        ):
            return item
    return None


async def build_real_execution_approval_transitions(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish immutable approval transition records."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or (
        "real-execution-approval-transition"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    real_execution_approval_id = _clean(
        getattr(args, "real_execution_approval_id", "")
    )
    to_status = _clean(getattr(args, "to_status", "")).lower() or "approved"

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    approvals = [
        item
        for item in records
        if item.get("type") == "replay_lifecycle_retry_real_execution_approval"
        and _matches_filters(
            item,
            real_execution_approval_id=real_execution_approval_id,
            rendered_command_id=rendered_command_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for approval in approvals:
        current_approval_id = _clean(approval.get("real_execution_approval_id"))

        if _find_existing_transition(
            records,
            real_execution_approval_id=current_approval_id,
            to_status=to_status,
        ):
            logger.info(
                "Skipping duplicate real execution approval transition: real_execution_approval_id=%s to_status=%s",
                current_approval_id,
                to_status,
            )
            continue

        record = build_real_execution_approval_transition_record(
            approval,
            to_status=to_status,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution approval transition: transition_id=%s from=%s to=%s real_execution_enabled=%s subprocess_enabled=%s",
            record.get("real_execution_approval_transition_id"),
            record.get("from_status"),
            record.get("to_status"),
            record.get("real_execution_enabled"),
            record.get("subprocess_enabled"),
        )

    logger.info(
        "Real execution approval transition builder completed: transitions=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build immutable fail-closed real execution approval transition records.",
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
        "--real-execution-approval-id",
        default="",
        help="Real execution approval id filter.",
    )
    parser.add_argument(
        "--to-status",
        default="approved",
        choices=("approved", "rejected"),
        help="Transition target status. Real execution remains disabled.",
    )
    parser.add_argument(
        "--source",
        default="real-execution-approval-transition",
        help="CRDT source/node id.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON records.")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_approval_transitions(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution approval transition builder completed: "
            f"transitions={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()