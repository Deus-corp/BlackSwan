"""Build actionable repair plans from read-only execution feedback.

This module consumes read-only feedback records and emits a non-executing repair
plan artifact for Overseer / Experience loop. It never invokes subprocesses and
never enables arbitrary real execution.
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

READ_ONLY_FEEDBACK_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_feedback"
)

READ_ONLY_REPAIR_PLAN_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_repair_plan"
)

KNOWN_REPAIR_TARGETS = {
    "execution_published": "publish_or_verify_execution_record",
    "execution_completed": "publish_or_verify_execution_completion",
    "evidence_published": "publish_or_verify_replay_evidence",
    "memory_record_published": "publish_or_verify_memory_record",
    "visibility_memory_summary_replay_evidence": (
        "refresh_or_verify_memory_replay_evidence_visibility"
    ),
    "visibility_crdt_trail_complete": "refresh_or_verify_crdt_trail_visibility",
    "scenario_seeded": "verify_scenario_seed",
    "directive_seeded": "verify_directive_seed",
    "visibility_security_lifecycle_validation": (
        "verify_security_lifecycle_validation_visibility"
    ),
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _failure_hints(feedback: Mapping[str, Any]) -> list[str]:
    raw = feedback.get("failure_hints")
    if not isinstance(raw, list):
        return []
    return sorted({_clean(item) for item in raw if _clean(item)})


def _extract_observed_markers(feedback: Mapping[str, Any]) -> list[str]:
    markers: list[str] = []
    for hint in _failure_hints(feedback):
        prefix = "observed_marker:"
        if hint.startswith(prefix):
            marker = _clean(hint[len(prefix) :])
            if marker:
                markers.append(marker)
    return sorted(set(markers))


def _build_repair_items(feedback: Mapping[str, Any]) -> list[dict[str, Any]]:
    markers = _extract_observed_markers(feedback)
    items: list[dict[str, Any]] = []

    source_status = _clean(feedback.get("source_status")) or "unknown"
    source_exit_code = feedback.get("source_exit_code")

    if source_status == "failed":
        for marker in markers:
            action = KNOWN_REPAIR_TARGETS.get(marker)
            if not action:
                continue
            items.append(
                {
                    "target": marker,
                    "recommended_action": action,
                    "priority": "high"
                    if marker
                    in {
                        "execution_published",
                        "execution_completed",
                        "evidence_published",
                        "memory_record_published",
                    }
                    else "medium",
                    "source": "read_only_execution_feedback",
                    "execution_required": False,
                    "subprocess_required": False,
                }
            )

    if not items and source_status == "failed":
        items.append(
            {
                "target": "read_only_execution_failure",
                "recommended_action": "inspect_failed_read_only_execution_result",
                "priority": "high",
                "source": "read_only_execution_feedback",
                "execution_required": False,
                "subprocess_required": False,
            }
        )

    if source_status == "rejected":
        items.append(
            {
                "target": "guarded_read_only_execution_rejection",
                "recommended_action": "resolve_guarded_read_only_execution_rejection",
                "priority": "high",
                "source": "read_only_execution_feedback",
                "execution_required": False,
                "subprocess_required": False,
            }
        )

    if source_status == "executed" and source_exit_code == 0:
        items.append(
            {
                "target": "successful_read_only_execution",
                "recommended_action": "promote_successful_read_only_execution_evidence",
                "priority": "low",
                "source": "read_only_execution_feedback",
                "execution_required": False,
                "subprocess_required": False,
            }
        )

    return items


def _plan_status(feedback: Mapping[str, Any], repair_items: list[Mapping[str, Any]]) -> str:
    feedback_status = _clean(feedback.get("feedback_status"))
    source_status = _clean(feedback.get("source_status"))

    if feedback_status == "actionable" and repair_items:
        return "planned"
    if feedback_status == "blocked":
        return "blocked"
    if feedback_status == "successful" or source_status == "executed":
        return "no_repair_needed"
    return "unknown"


def build_real_execution_read_only_repair_plan_record(
    feedback: Mapping[str, Any],
    *,
    source: str = "real-execution-read-only-repair-plan",
) -> dict[str, Any]:
    feedback_id = _clean(feedback.get("real_execution_read_only_feedback_id"))
    execution_result_id = _clean(
        feedback.get("real_execution_read_only_execution_result_id")
    )
    rendered_command_id = _clean(feedback.get("rendered_command_id"))

    if not feedback_id:
        raise ValueError("real_execution_read_only_feedback_id is required")
    if not execution_result_id:
        raise ValueError("real_execution_read_only_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    repair_items = _build_repair_items(feedback)
    plan_status = _plan_status(feedback, repair_items)
    recommended_next_action = _clean(feedback.get("recommended_next_action")) or "unknown"

    repair_plan_id = _stable_id(
        "replay-retry-real-read-only-repair-plan",
        feedback_id,
        execution_result_id,
        rendered_command_id,
        plan_status,
        recommended_next_action,
    )

    payload = {
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": execution_result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            feedback.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            feedback.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            feedback.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            feedback.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            feedback.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            feedback.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            feedback.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            feedback.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(feedback.get("plan_id")),
        "proposal_id": _clean(feedback.get("proposal_id")),
        "approval_id": _clean(feedback.get("approval_id")),
        "timeout_profile": _clean(feedback.get("timeout_profile")) or "standard",
        "decision_mode": _clean(feedback.get("decision_mode")) or "manual",
        "source_feedback_status": _clean(feedback.get("feedback_status")) or "unknown",
        "source_status": _clean(feedback.get("source_status")) or "unknown",
        "source_exit_code": feedback.get("source_exit_code"),
        "source_recommended_next_action": recommended_next_action,
        "repair_plan_status": plan_status,
        "repair_items": repair_items,
        "repair_item_count": len(repair_items),
        "repair_targets": [item["target"] for item in repair_items],
        "recommended_next_action": "review_replay_evidence_repair_plan",
        "requires_operator_review": True,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "read_only_execution_repair_plan_recorded",
    }

    return {
        "type": READ_ONLY_REPAIR_PLAN_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    feedback_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        feedback_id
        and _clean(record.get("real_execution_read_only_feedback_id")) != feedback_id
    ):
        return False
    return True


def _find_existing_repair_plan(
    records: list[Mapping[str, Any]],
    *,
    feedback_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != READ_ONLY_REPAIR_PLAN_TYPE:
            continue
        if _clean(item.get("real_execution_read_only_feedback_id")) == feedback_id:
            return item
    return None


async def build_real_execution_read_only_repair_plan_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-read-only-repair-plan"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    feedback_id = _clean(getattr(args, "real_execution_read_only_feedback_id", ""))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    feedback_records = [
        item
        for item in records
        if item.get("type") == READ_ONLY_FEEDBACK_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            feedback_id=feedback_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for feedback in feedback_records:
        current_feedback_id = _clean(feedback.get("real_execution_read_only_feedback_id"))
        if _find_existing_repair_plan(records, feedback_id=current_feedback_id):
            logger.info(
                "Skipping duplicate read-only repair plan: feedback_id=%s",
                current_feedback_id,
            )
            continue

        record = build_real_execution_read_only_repair_plan_record(
            feedback,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only repair plan: repair_plan_id=%s status=%s repair_items=%s",
            record.get("real_execution_read_only_repair_plan_id"),
            record.get("repair_plan_status"),
            record.get("repair_item_count"),
        )

    logger.info(
        "Read-only repair plan builder completed: repair_plans=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build actionable repair plans from read-only execution feedback.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-feedback-id", default="")
    parser.add_argument("--source", default="real-execution-read-only-repair-plan")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_repair_plan_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Read-only repair plan builder completed: repair_plans={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()