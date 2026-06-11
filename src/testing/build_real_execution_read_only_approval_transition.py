"""Build immutable read-only execution approval transition records.

This records a transition from pending to approved/rejected for future read-only
execution. It never enables execution and never invokes subprocesses.
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

REAL_READ_ONLY_APPROVAL_TRANSITION_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_approval_transition"
)

TRANSITION_TARGET_STATUSES = {"approved", "rejected"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_read_only_approval_transition_record(
    approval: Mapping[str, Any],
    *,
    to_status: str = "approved",
    source: str = "real-execution-read-only-approval-transition",
) -> dict[str, Any]:
    target_status = _clean(to_status) or "approved"
    if target_status not in TRANSITION_TARGET_STATUSES:
        raise ValueError(f"unsupported to_status: {target_status}")

    from_status = _clean(approval.get("approval_status")) or "unknown"
    if from_status != "pending":
        raise ValueError(f"read-only approval transition requires pending source: {from_status}")

    read_only_approval_id = _clean(
        approval.get("real_execution_read_only_approval_id")
    )
    read_only_final_gate_id = _clean(
        approval.get("real_execution_read_only_final_gate_id")
    )
    read_only_promotion_id = _clean(
        approval.get("real_execution_read_only_promotion_id")
    )
    noop_result_id = _clean(approval.get("real_execution_noop_result_id"))
    dry_run_envelope_id = _clean(
        approval.get("real_execution_dry_run_envelope_id")
    )
    real_final_gate_id = _clean(approval.get("real_execution_final_gate_id"))
    real_approval_transition_id = _clean(
        approval.get("real_execution_approval_transition_id")
    )
    real_approval_id = _clean(approval.get("real_execution_approval_id"))
    preflight_id = _clean(approval.get("real_execution_preflight_id"))
    controlled_result_id = _clean(approval.get("controlled_execution_result_id"))
    rendered_command_id = _clean(approval.get("rendered_command_id"))
    plan_id = _clean(approval.get("plan_id"))
    proposal_id = _clean(approval.get("proposal_id"))
    approval_id = _clean(approval.get("approval_id"))
    timeout_profile = _clean(approval.get("timeout_profile")) or "standard"
    decision_mode = _clean(approval.get("decision_mode")) or "manual"

    read_only_command = _clean(approval.get("read_only_command"))
    read_only_module = _clean(approval.get("read_only_module"))
    read_only_argv = approval.get("read_only_argv")

    if not read_only_approval_id:
        raise ValueError("real_execution_read_only_approval_id is required")
    if not read_only_final_gate_id:
        raise ValueError("real_execution_read_only_final_gate_id is required")
    if not read_only_promotion_id:
        raise ValueError("real_execution_read_only_promotion_id is required")
    if not noop_result_id:
        raise ValueError("real_execution_noop_result_id is required")
    if not dry_run_envelope_id:
        raise ValueError("real_execution_dry_run_envelope_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    transition_id = _stable_id(
        "replay-retry-real-read-only-approval-transition",
        read_only_approval_id,
        read_only_final_gate_id,
        rendered_command_id,
        from_status,
        target_status,
    )

    payload = {
        "real_execution_read_only_approval_transition_id": transition_id,
        "real_execution_read_only_approval_id": read_only_approval_id,
        "real_execution_read_only_final_gate_id": read_only_final_gate_id,
        "real_execution_read_only_promotion_id": read_only_promotion_id,
        "real_execution_noop_result_id": noop_result_id,
        "real_execution_dry_run_envelope_id": dry_run_envelope_id,
        "real_execution_final_gate_id": real_final_gate_id,
        "real_execution_approval_transition_id": real_approval_transition_id,
        "real_execution_approval_id": real_approval_id,
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "from_status": from_status,
        "to_status": target_status,
        "read_only_command": read_only_command,
        "read_only_module": read_only_module,
        "read_only_argv": read_only_argv if isinstance(read_only_argv, list) else [],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_approval_transition_recorded",
    }

    return {
        "type": REAL_READ_ONLY_APPROVAL_TRANSITION_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    real_execution_read_only_approval_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        real_execution_read_only_approval_id
        and _clean(record.get("real_execution_read_only_approval_id"))
        != real_execution_read_only_approval_id
    ):
        return False
    return True


def _find_existing_transition(
    records: list[Mapping[str, Any]],
    *,
    read_only_approval_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_READ_ONLY_APPROVAL_TRANSITION_TYPE:
            continue
        if (
            _clean(item.get("real_execution_read_only_approval_id"))
            == read_only_approval_id
        ):
            return item
    return None


async def build_real_execution_read_only_approval_transitions(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or (
        "real-execution-read-only-approval-transition"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    read_only_approval_id = _clean(
        getattr(args, "real_execution_read_only_approval_id", "")
    )
    to_status = _clean(getattr(args, "to_status", "")) or "approved"

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    approvals = [
        item
        for item in records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_approval"
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            real_execution_read_only_approval_id=read_only_approval_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for approval in approvals:
        current_approval_id = _clean(
            approval.get("real_execution_read_only_approval_id")
        )
        if _find_existing_transition(
            records,
            read_only_approval_id=current_approval_id,
        ):
            logger.info(
                "Skipping duplicate read-only approval transition: approval_id=%s",
                current_approval_id,
            )
            continue

        record = build_real_execution_read_only_approval_transition_record(
            approval,
            to_status=to_status,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only approval transition: transition_id=%s from=%s to=%s execution_enabled=%s subprocess_enabled=%s",
            record.get("real_execution_read_only_approval_transition_id"),
            record.get("from_status"),
            record.get("to_status"),
            record.get("read_only_execution_enabled"),
            record.get("subprocess_enabled"),
        )

    logger.info(
        "Read-only approval transition builder completed: transitions=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build immutable read-only execution approval transition records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-approval-id", default="")
    parser.add_argument(
        "--to-status",
        default="approved",
        choices=sorted(TRANSITION_TARGET_STATUSES),
    )
    parser.add_argument(
        "--source",
        default="real-execution-read-only-approval-transition",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_approval_transitions(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Read-only approval transition builder completed: "
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