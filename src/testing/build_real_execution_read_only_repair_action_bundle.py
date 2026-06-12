"""Build reviewed repair action bundles from read-only repair plans.

This module consumes a read-only repair plan and emits a review-only action
bundle. It never executes repair actions, never invokes subprocesses, and never
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

READ_ONLY_REPAIR_PLAN_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_repair_plan"
)

READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _repair_items(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in _safe_list(plan.get("repair_items")) if isinstance(item, Mapping)]


def _build_bundle_items(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for index, item in enumerate(_repair_items(plan), start=1):
        target = _clean(item.get("target")) or f"repair_target_{index}"
        recommended_action = _clean(item.get("recommended_action")) or "review_repair_target"
        priority = _clean(item.get("priority")) or "medium"

        items.append(
            {
                "action_id": _stable_id("read-only-repair-action", target, recommended_action),
                "sequence": index,
                "target": target,
                "recommended_action": recommended_action,
                "priority": priority,
                "source": _clean(item.get("source")) or "read_only_repair_plan",
                "review_required": True,
                "execution_allowed": False,
                "subprocess_allowed": False,
                "real_execution_allowed": False,
                "execution_performed": False,
                "subprocess_invoked": False,
            }
        )

    if not items:
        items.append(
            {
                "action_id": _stable_id(
                    "read-only-repair-action",
                    "manual_review",
                    plan.get("real_execution_read_only_repair_plan_id"),
                ),
                "sequence": 1,
                "target": "manual_repair_plan_review",
                "recommended_action": "review_replay_evidence_repair_plan",
                "priority": "high",
                "source": "read_only_repair_plan",
                "review_required": True,
                "execution_allowed": False,
                "subprocess_allowed": False,
                "real_execution_allowed": False,
                "execution_performed": False,
                "subprocess_invoked": False,
            }
        )

    return items


def build_real_execution_read_only_repair_action_bundle_record(
    repair_plan: Mapping[str, Any],
    *,
    source: str = "real-execution-read-only-repair-action-bundle",
) -> dict[str, Any]:
    repair_plan_id = _clean(repair_plan.get("real_execution_read_only_repair_plan_id"))
    feedback_id = _clean(repair_plan.get("real_execution_read_only_feedback_id"))
    execution_result_id = _clean(
        repair_plan.get("real_execution_read_only_execution_result_id")
    )
    rendered_command_id = _clean(repair_plan.get("rendered_command_id"))

    if not repair_plan_id:
        raise ValueError("real_execution_read_only_repair_plan_id is required")
    if not feedback_id:
        raise ValueError("real_execution_read_only_feedback_id is required")
    if not execution_result_id:
        raise ValueError("real_execution_read_only_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    bundle_items = _build_bundle_items(repair_plan)
    bundle_id = _stable_id(
        "replay-retry-real-read-only-repair-action-bundle",
        repair_plan_id,
        feedback_id,
        execution_result_id,
        rendered_command_id,
    )

    source_repair_plan_status = _clean(repair_plan.get("repair_plan_status")) or "unknown"
    bundle_status = (
        "assembled"
        if source_repair_plan_status in {"planned", "blocked", "no_repair_needed"}
        else "unknown"
    )

    payload = {
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": execution_result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_plan.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_plan.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_plan.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_plan.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_plan.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_plan.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_plan.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_plan.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_plan.get("plan_id")),
        "proposal_id": _clean(repair_plan.get("proposal_id")),
        "approval_id": _clean(repair_plan.get("approval_id")),
        "timeout_profile": _clean(repair_plan.get("timeout_profile")) or "standard",
        "decision_mode": _clean(repair_plan.get("decision_mode")) or "manual",
        "source_repair_plan_status": source_repair_plan_status,
        "source_feedback_status": _clean(repair_plan.get("source_feedback_status")) or "unknown",
        "source_status": _clean(repair_plan.get("source_status")) or "unknown",
        "source_exit_code": repair_plan.get("source_exit_code"),
        "source_repair_item_count": repair_plan.get("repair_item_count"),
        "bundle_status": bundle_status,
        "bundle_items": bundle_items,
        "bundle_item_count": len(bundle_items),
        "bundle_targets": [item["target"] for item in bundle_items],
        "recommended_next_action": "review_repair_action_bundle",
        "requires_operator_review": True,
        "bundle_reviewed": False,
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
        "reason": "read_only_repair_action_bundle_recorded",
    }

    return {
        "type": READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    repair_plan_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        repair_plan_id
        and _clean(record.get("real_execution_read_only_repair_plan_id"))
        != repair_plan_id
    ):
        return False
    return True


def _find_existing_bundle(
    records: list[Mapping[str, Any]],
    *,
    repair_plan_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != READ_ONLY_REPAIR_ACTION_BUNDLE_TYPE:
            continue
        if _clean(item.get("real_execution_read_only_repair_plan_id")) == repair_plan_id:
            return item
    return None


async def build_real_execution_read_only_repair_action_bundle_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-read-only-repair-action-bundle"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    repair_plan_id = _clean(
        getattr(args, "real_execution_read_only_repair_plan_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    repair_plans = [
        item
        for item in records
        if item.get("type") == READ_ONLY_REPAIR_PLAN_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            repair_plan_id=repair_plan_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for repair_plan in repair_plans:
        current_repair_plan_id = _clean(
            repair_plan.get("real_execution_read_only_repair_plan_id")
        )
        if _find_existing_bundle(records, repair_plan_id=current_repair_plan_id):
            logger.info(
                "Skipping duplicate read-only repair action bundle: repair_plan_id=%s",
                current_repair_plan_id,
            )
            continue

        record = build_real_execution_read_only_repair_action_bundle_record(
            repair_plan,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only repair action bundle: bundle_id=%s status=%s items=%s",
            record.get("real_execution_read_only_repair_action_bundle_id"),
            record.get("bundle_status"),
            record.get("bundle_item_count"),
        )

    logger.info(
        "Read-only repair action bundle builder completed: bundles=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build reviewed repair action bundles from read-only repair plans.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-repair-plan-id", default="")
    parser.add_argument(
        "--source",
        default="real-execution-read-only-repair-action-bundle",
    )
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_repair_action_bundle_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Read-only repair action bundle builder completed: "
            f"bundles={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()