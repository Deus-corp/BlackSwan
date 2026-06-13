"""Build explicit repair execution approval scaffold records.

Consumes an approved read-only repair action bundle review and emits a pending
repair execution approval artifact. This scaffold never executes repair actions,
never invokes subprocesses, and never enables arbitrary real execution.
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

REPAIR_ACTION_BUNDLE_REVIEW_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
)

REPAIR_EXECUTION_APPROVAL_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_approval"
)

ALLOWED_APPROVAL_STATUSES = {"pending", "approved", "rejected"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_targets(review: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(review.get("source_bundle_targets"))
            if _clean(item)
        }
    )


def build_real_execution_repair_approval_record(
    repair_action_bundle_review: Mapping[str, Any],
    *,
    approval_status: str = "pending",
    operator_authorized: bool = True,
    source: str = "real-execution-repair-approval",
) -> dict[str, Any]:
    review_id = _clean(
        repair_action_bundle_review.get(
            "real_execution_read_only_repair_action_bundle_review_id"
        )
    )
    bundle_id = _clean(
        repair_action_bundle_review.get(
            "real_execution_read_only_repair_action_bundle_id"
        )
    )
    repair_plan_id = _clean(
        repair_action_bundle_review.get("real_execution_read_only_repair_plan_id")
    )
    feedback_id = _clean(
        repair_action_bundle_review.get("real_execution_read_only_feedback_id")
    )
    read_only_execution_result_id = _clean(
        repair_action_bundle_review.get(
            "real_execution_read_only_execution_result_id"
        )
    )
    rendered_command_id = _clean(repair_action_bundle_review.get("rendered_command_id"))
    clean_approval_status = _clean(approval_status) or "pending"

    if clean_approval_status not in ALLOWED_APPROVAL_STATUSES:
        raise ValueError("approval_status must be one of: pending, approved, rejected")
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
        raise ValueError(
            "real_execution_read_only_execution_result_id is required"
        )
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    source_review_status = _clean(
        repair_action_bundle_review.get("review_status")
    ) or "unknown"
    source_review_approved = bool(repair_action_bundle_review.get("review_approved"))
    source_reviewed = bool(repair_action_bundle_review.get("reviewed"))

    if source_review_status != "approved" or not source_reviewed or not source_review_approved:
        raise ValueError("repair action bundle review must be approved")

    approval_id = _stable_id(
        "replay-retry-real-repair-approval",
        review_id,
        bundle_id,
        repair_plan_id,
        read_only_execution_result_id,
        rendered_command_id,
        clean_approval_status,
    )

    payload = {
        "real_execution_repair_approval_id": approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": review_id,
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": read_only_execution_result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_action_bundle_review.get(
                "real_execution_read_only_readiness_gate_id"
            )
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_action_bundle_review.get(
                "real_execution_read_only_approval_transition_id"
            )
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_action_bundle_review.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_action_bundle_review.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_action_bundle_review.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_action_bundle_review.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_action_bundle_review.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_action_bundle_review.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_action_bundle_review.get("plan_id")),
        "proposal_id": _clean(repair_action_bundle_review.get("proposal_id")),
        "approval_id": _clean(repair_action_bundle_review.get("approval_id")),
        "timeout_profile": _clean(
            repair_action_bundle_review.get("timeout_profile")
        )
        or "standard",
        "decision_mode": _clean(repair_action_bundle_review.get("decision_mode"))
        or "manual",
        "source_review_status": source_review_status,
        "source_reviewed": source_reviewed,
        "source_review_approved": source_review_approved,
        "source_bundle_status": _clean(
            repair_action_bundle_review.get("source_bundle_status")
        )
        or "unknown",
        "source_repair_plan_status": _clean(
            repair_action_bundle_review.get("source_repair_plan_status")
        )
        or "unknown",
        "source_feedback_status": _clean(
            repair_action_bundle_review.get("source_feedback_status")
        )
        or "unknown",
        "source_status": _clean(repair_action_bundle_review.get("source_status"))
        or "unknown",
        "source_exit_code": repair_action_bundle_review.get("source_exit_code"),
        "source_bundle_item_count": repair_action_bundle_review.get(
            "source_bundle_item_count"
        ),
        "source_bundle_targets": _source_targets(repair_action_bundle_review),
        "approval_status": clean_approval_status,
        "operator_authorized": bool(operator_authorized),
        "requires_operator_review": True,
        "repair_execution_approval_required": True,
        "repair_execution_approved": clean_approval_status == "approved",
        "repair_execution_rejected": clean_approval_status == "rejected",
        "recommended_next_action": (
            "await_repair_execution_approval_transition"
            if clean_approval_status == "approved"
            else "await_repair_execution_approval"
            if clean_approval_status == "pending"
            else "revise_repair_action_bundle"
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
        "reason": "repair_execution_explicit_approval_required",
    }

    return {
        "type": REPAIR_EXECUTION_APPROVAL_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    review_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        review_id
        and _clean(
            record.get("real_execution_read_only_repair_action_bundle_review_id")
        )
        != review_id
    ):
        return False
    return True


def _find_existing_approval(
    records: list[Mapping[str, Any]],
    *,
    review_id: str,
    approval_status: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_EXECUTION_APPROVAL_TYPE:
            continue
        if (
            _clean(
                item.get("real_execution_read_only_repair_action_bundle_review_id")
            )
            == review_id
            and _clean(item.get("approval_status")) == approval_status
        ):
            return item
    return None


async def build_real_execution_repair_approval_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-repair-approval"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    review_id = _clean(
        getattr(args, "real_execution_read_only_repair_action_bundle_review_id", "")
    )
    approval_status = _clean(getattr(args, "approval_status", "")) or "pending"
    operator_authorized = bool(getattr(args, "operator_authorized", True))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    reviews = [
        item
        for item in records
        if item.get("type") == REPAIR_ACTION_BUNDLE_REVIEW_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            review_id=review_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for review in reviews:
        current_review_id = _clean(
            review.get("real_execution_read_only_repair_action_bundle_review_id")
        )
        if _find_existing_approval(
            records,
            review_id=current_review_id,
            approval_status=approval_status,
        ):
            logger.info(
                "Skipping duplicate repair execution approval: review_id=%s "
                "approval_status=%s",
                current_review_id,
                approval_status,
            )
            continue

        record = build_real_execution_repair_approval_record(
            review,
            approval_status=approval_status,
            operator_authorized=operator_authorized,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published repair execution approval scaffold: approval_id=%s "
            "status=%s repair_execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_repair_approval_id"),
            record.get("approval_status"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info("Repair execution approval builder completed: approvals=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build explicit repair execution approval scaffold records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument(
        "--real-execution-read-only-repair-action-bundle-review-id",
        default="",
    )
    parser.add_argument(
        "--approval-status",
        choices=sorted(ALLOWED_APPROVAL_STATUSES),
        default="pending",
    )
    parser.add_argument("--operator-authorized", action="store_true", default=True)
    parser.add_argument("--source", default="real-execution-repair-approval")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_repair_approval_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Repair execution approval builder completed: approvals={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()