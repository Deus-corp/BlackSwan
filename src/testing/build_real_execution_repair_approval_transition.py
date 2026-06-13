"""Build immutable repair execution approval transition records.

Consumes a pending repair execution approval scaffold and emits an immutable
transition artifact. This transition may approve or reject the repair approval,
but it never executes repair actions, never invokes subprocesses, and never
enables arbitrary real execution.
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

REPAIR_EXECUTION_APPROVAL_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_approval"
)

REPAIR_EXECUTION_APPROVAL_TRANSITION_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_approval_transition"
)

ALLOWED_TO_STATUSES = {"approved", "rejected"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_targets(approval: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(approval.get("source_bundle_targets"))
            if _clean(item)
        }
    )


def build_real_execution_repair_approval_transition_record(
    repair_approval: Mapping[str, Any],
    *,
    to_status: str = "approved",
    operator_authorized: bool = True,
    source: str = "real-execution-repair-approval-transition",
) -> dict[str, Any]:
    repair_approval_id = _clean(
        repair_approval.get("real_execution_repair_approval_id")
    )
    review_id = _clean(
        repair_approval.get("real_execution_read_only_repair_action_bundle_review_id")
    )
    bundle_id = _clean(
        repair_approval.get("real_execution_read_only_repair_action_bundle_id")
    )
    repair_plan_id = _clean(
        repair_approval.get("real_execution_read_only_repair_plan_id")
    )
    feedback_id = _clean(repair_approval.get("real_execution_read_only_feedback_id"))
    read_only_execution_result_id = _clean(
        repair_approval.get("real_execution_read_only_execution_result_id")
    )
    rendered_command_id = _clean(repair_approval.get("rendered_command_id"))

    from_status = _clean(repair_approval.get("approval_status")) or "unknown"
    clean_to_status = _clean(to_status) or "approved"

    if clean_to_status not in ALLOWED_TO_STATUSES:
        raise ValueError("to_status must be one of: approved, rejected")
    if from_status != "pending":
        raise ValueError("repair approval transition requires pending source approval")
    if not repair_approval_id:
        raise ValueError("real_execution_repair_approval_id is required")
    if not review_id:
        raise ValueError(
            "real_execution_read_only_repair_action_bundle_review_id is required"
        )
    if not bundle_id:
        raise ValueError(
            "real_execution_read_only_repair_action_bundle_id is required"
        )
    if not repair_plan_id:
        raise ValueError("real_execution_read_only_repair_plan_id is required")
    if not feedback_id:
        raise ValueError("real_execution_read_only_feedback_id is required")
    if not read_only_execution_result_id:
        raise ValueError("real_execution_read_only_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    source_review_status = _clean(repair_approval.get("source_review_status"))
    source_reviewed = bool(repair_approval.get("source_reviewed"))
    source_review_approved = bool(repair_approval.get("source_review_approved"))
    approval_required = bool(repair_approval.get("repair_execution_approval_required"))

    if source_review_status != "approved" or not source_reviewed or not source_review_approved:
        raise ValueError("repair approval transition requires approved source review")
    if not approval_required:
        raise ValueError("repair approval transition requires approval_required source")

    transition_id = _stable_id(
        "replay-retry-real-repair-approval-transition",
        repair_approval_id,
        review_id,
        bundle_id,
        repair_plan_id,
        rendered_command_id,
        from_status,
        clean_to_status,
    )

    payload = {
        "real_execution_repair_approval_transition_id": transition_id,
        "real_execution_repair_approval_id": repair_approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": review_id,
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": read_only_execution_result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_approval.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_approval.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_approval.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_approval.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_approval.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_approval.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_approval.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_approval.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_approval.get("plan_id")),
        "proposal_id": _clean(repair_approval.get("proposal_id")),
        "approval_id": _clean(repair_approval.get("approval_id")),
        "timeout_profile": _clean(repair_approval.get("timeout_profile")) or "standard",
        "decision_mode": _clean(repair_approval.get("decision_mode")) or "manual",
        "from_status": from_status,
        "to_status": clean_to_status,
        "source_approval_status": from_status,
        "source_review_status": source_review_status,
        "source_reviewed": source_reviewed,
        "source_review_approved": source_review_approved,
        "source_bundle_status": _clean(repair_approval.get("source_bundle_status"))
        or "unknown",
        "source_repair_plan_status": _clean(
            repair_approval.get("source_repair_plan_status")
        )
        or "unknown",
        "source_feedback_status": _clean(
            repair_approval.get("source_feedback_status")
        )
        or "unknown",
        "source_status": _clean(repair_approval.get("source_status")) or "unknown",
        "source_exit_code": repair_approval.get("source_exit_code"),
        "source_bundle_item_count": repair_approval.get("source_bundle_item_count"),
        "source_bundle_targets": _source_targets(repair_approval),
        "operator_authorized": bool(operator_authorized),
        "requires_operator_review": True,
        "repair_execution_approval_required": True,
        "repair_execution_transition_approved": clean_to_status == "approved",
        "repair_execution_transition_rejected": clean_to_status == "rejected",
        "recommended_next_action": (
            "prepare_repair_execution_final_gate"
            if clean_to_status == "approved"
            else "revise_repair_execution_approval"
        ),
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_approval_transition_recorded",
    }

    return {
        "type": REPAIR_EXECUTION_APPROVAL_TRANSITION_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    repair_approval_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        repair_approval_id
        and _clean(record.get("real_execution_repair_approval_id"))
        != repair_approval_id
    ):
        return False
    return True


def _find_existing_transition(
    records: list[Mapping[str, Any]],
    *,
    repair_approval_id: str,
    to_status: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_EXECUTION_APPROVAL_TRANSITION_TYPE:
            continue
        if (
            _clean(item.get("real_execution_repair_approval_id"))
            == repair_approval_id
            and _clean(item.get("to_status")) == to_status
        ):
            return item
    return None


async def build_real_execution_repair_approval_transition_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-repair-approval-transition"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    repair_approval_id = _clean(getattr(args, "real_execution_repair_approval_id", ""))
    to_status = _clean(getattr(args, "to_status", "")) or "approved"
    operator_authorized = bool(getattr(args, "operator_authorized", True))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    approvals = [
        item
        for item in records
        if item.get("type") == REPAIR_EXECUTION_APPROVAL_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            repair_approval_id=repair_approval_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for approval in approvals:
        current_approval_id = _clean(approval.get("real_execution_repair_approval_id"))
        if _find_existing_transition(
            records,
            repair_approval_id=current_approval_id,
            to_status=to_status,
        ):
            logger.info(
                "Skipping duplicate repair execution approval transition: "
                "approval_id=%s to_status=%s",
                current_approval_id,
                to_status,
            )
            continue

        record = build_real_execution_repair_approval_transition_record(
            approval,
            to_status=to_status,
            operator_authorized=operator_authorized,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published repair execution approval transition: transition_id=%s "
            "from=%s to=%s repair_execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_repair_approval_transition_id"),
            record.get("from_status"),
            record.get("to_status"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info(
        "Repair execution approval transition builder completed: transitions=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build immutable repair execution approval transition records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-repair-approval-id", default="")
    parser.add_argument(
        "--to-status",
        choices=sorted(ALLOWED_TO_STATUSES),
        default="approved",
    )
    parser.add_argument("--operator-authorized", action="store_true", default=True)
    parser.add_argument(
        "--source",
        default="real-execution-repair-approval-transition",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_repair_approval_transition_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Repair execution approval transition builder completed: "
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