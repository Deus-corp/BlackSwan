"""Build explicit operator review records for read-only repair action bundles.

This module consumes a read-only repair action bundle and emits an immutable
operator review artifact. It never executes bundle actions, never invokes
subprocesses, and never enables arbitrary real execution.
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

READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
)

READ_ONLY_REPAIR_ACTION_BUNDLE_REVIEW_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
)

ALLOWED_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _bundle_targets(bundle: Mapping[str, Any]) -> list[str]:
    return sorted({_clean(item) for item in _safe_list(bundle.get("bundle_targets")) if _clean(item)})


def build_real_execution_read_only_repair_action_bundle_review_record(
    repair_action_bundle: Mapping[str, Any],
    *,
    review_status: str = "pending",
    operator_authorized: bool = True,
    source: str = "real-execution-read-only-repair-action-bundle-review",
) -> dict[str, Any]:
    bundle_id = _clean(
        repair_action_bundle.get("real_execution_read_only_repair_action_bundle_id")
    )
    repair_plan_id = _clean(
        repair_action_bundle.get("real_execution_read_only_repair_plan_id")
    )
    feedback_id = _clean(
        repair_action_bundle.get("real_execution_read_only_feedback_id")
    )
    execution_result_id = _clean(
        repair_action_bundle.get("real_execution_read_only_execution_result_id")
    )
    rendered_command_id = _clean(repair_action_bundle.get("rendered_command_id"))
    clean_review_status = _clean(review_status) or "pending"

    if clean_review_status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(
            "review_status must be one of: pending, approved, rejected"
        )
    if not bundle_id:
        raise ValueError(
            "real_execution_read_only_repair_action_bundle_id is required"
        )
    if not repair_plan_id:
        raise ValueError("real_execution_read_only_repair_plan_id is required")
    if not feedback_id:
        raise ValueError("real_execution_read_only_feedback_id is required")
    if not execution_result_id:
        raise ValueError(
            "real_execution_read_only_execution_result_id is required"
        )
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    review_id = _stable_id(
        "replay-retry-real-read-only-repair-action-bundle-review",
        bundle_id,
        repair_plan_id,
        feedback_id,
        rendered_command_id,
        clean_review_status,
        operator_authorized,
    )

    bundle_item_count = repair_action_bundle.get("bundle_item_count")
    source_bundle_status = (
        _clean(repair_action_bundle.get("bundle_status")) or "unknown"
    )

    payload = {
        "real_execution_read_only_repair_action_bundle_review_id": review_id,
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": execution_result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_action_bundle.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_action_bundle.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_action_bundle.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_action_bundle.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_action_bundle.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_action_bundle.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_action_bundle.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_action_bundle.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_action_bundle.get("plan_id")),
        "proposal_id": _clean(repair_action_bundle.get("proposal_id")),
        "approval_id": _clean(repair_action_bundle.get("approval_id")),
        "timeout_profile": _clean(repair_action_bundle.get("timeout_profile")) or "standard",
        "decision_mode": _clean(repair_action_bundle.get("decision_mode")) or "manual",
        "source_bundle_status": source_bundle_status,
        "source_repair_plan_status": _clean(
            repair_action_bundle.get("source_repair_plan_status")
        )
        or "unknown",
        "source_feedback_status": _clean(
            repair_action_bundle.get("source_feedback_status")
        )
        or "unknown",
        "source_status": _clean(repair_action_bundle.get("source_status")) or "unknown",
        "source_exit_code": repair_action_bundle.get("source_exit_code"),
        "source_bundle_item_count": (
            bundle_item_count if isinstance(bundle_item_count, int) else 0
        ),
        "source_bundle_targets": _bundle_targets(repair_action_bundle),
        "review_status": clean_review_status,
        "operator_authorized": bool(operator_authorized),
        "requires_operator_review": True,
        "reviewed": clean_review_status in {"approved", "rejected"},
        "review_approved": clean_review_status == "approved",
        "review_rejected": clean_review_status == "rejected",
        "recommended_next_action": (
            "prepare_repair_execution_approval_scaffold"
            if clean_review_status == "approved"
            else "await_repair_action_bundle_review"
            if clean_review_status == "pending"
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
        "reason": "read_only_repair_action_bundle_review_recorded",
    }

    return {
        "type": READ_ONLY_REPAIR_ACTION_BUNDLE_REVIEW_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    bundle_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        bundle_id
        and _clean(record.get("real_execution_read_only_repair_action_bundle_id"))
        != bundle_id
    ):
        return False
    return True


def _find_existing_review(
    records: list[Mapping[str, Any]],
    *,
    bundle_id: str,
    review_status: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != READ_ONLY_REPAIR_ACTION_BUNDLE_REVIEW_TYPE:
            continue
        if (
            _clean(item.get("real_execution_read_only_repair_action_bundle_id"))
            == bundle_id
            and _clean(item.get("review_status")) == review_status
        ):
            return item
    return None


async def build_real_execution_read_only_repair_action_bundle_review_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-read-only-repair-action-bundle-review"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    bundle_id = _clean(
        getattr(args, "real_execution_read_only_repair_action_bundle_id", "")
    )
    review_status = _clean(getattr(args, "review_status", "")) or "pending"
    operator_authorized = bool(getattr(args, "operator_authorized", True))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    bundles = [
        item
        for item in records
        if item.get("type") == READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            bundle_id=bundle_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for bundle in bundles:
        current_bundle_id = _clean(
            bundle.get("real_execution_read_only_repair_action_bundle_id")
        )
        if _find_existing_review(
            records,
            bundle_id=current_bundle_id,
            review_status=review_status,
        ):
            logger.info(
                "Skipping duplicate read-only repair action bundle review: "
                "bundle_id=%s review_status=%s",
                current_bundle_id,
                review_status,
            )
            continue

        record = build_real_execution_read_only_repair_action_bundle_review_record(
            bundle,
            review_status=review_status,
            operator_authorized=operator_authorized,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only repair action bundle review: review_id=%s "
            "status=%s execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_read_only_repair_action_bundle_review_id"),
            record.get("review_status"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info(
        "Read-only repair action bundle review builder completed: reviews=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build explicit operator review records for read-only repair "
            "action bundles."
        ),
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument(
        "--real-execution-read-only-repair-action-bundle-id",
        default="",
    )
    parser.add_argument(
        "--review-status",
        choices=sorted(ALLOWED_REVIEW_STATUSES),
        default="pending",
    )
    parser.add_argument(
        "--operator-authorized",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--source",
        default="real-execution-read-only-repair-action-bundle-review",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_repair_action_bundle_review_records(
        args
    )

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Read-only repair action bundle review builder completed: "
            f"reviews={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()