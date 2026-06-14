"""Build repair execution readiness gate records.

Consumes actionable repair noop feedback and emits a ready-blocked repair
readiness gate. This gate proves the repair path is ready for a later guarded
execution PR, but it never executes repair actions, never invokes subprocesses,
and never enables repair execution.
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

REPAIR_NOOP_FEEDBACK_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_noop_feedback"
)

REPAIR_READINESS_GATE_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_readiness_gate"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_targets(feedback: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(feedback.get("source_repair_dry_run_targets"))
            if _clean(item)
        }
    )


def _validate_feedback_preconditions(feedback: Mapping[str, Any]) -> None:
    feedback_id = _clean(feedback.get("real_execution_repair_noop_feedback_id"))
    noop_result_id = _clean(feedback.get("real_execution_repair_noop_result_id"))
    envelope_id = _clean(feedback.get("real_execution_repair_dry_run_envelope_id"))
    final_gate_id = _clean(feedback.get("real_execution_repair_final_gate_id"))
    rendered_command_id = _clean(feedback.get("rendered_command_id"))

    if not feedback_id:
        raise ValueError("real_execution_repair_noop_feedback_id is required")
    if not noop_result_id:
        raise ValueError("real_execution_repair_noop_result_id is required")
    if not envelope_id:
        raise ValueError("real_execution_repair_dry_run_envelope_id is required")
    if not final_gate_id:
        raise ValueError("real_execution_repair_final_gate_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    if _clean(feedback.get("feedback_status")) != "actionable":
        raise ValueError("repair readiness gate requires actionable feedback")
    if not bool(feedback.get("repair_noop_verified")):
        raise ValueError("repair readiness gate requires verified repair noop")
    if not bool(feedback.get("repair_path_can_proceed")):
        raise ValueError("repair readiness gate requires repair path can proceed")
    if not bool(feedback.get("repair_path_next_gate_allowed")):
        raise ValueError("repair readiness gate requires next gate allowed")
    if (
        _clean(feedback.get("recommended_next_action"))
        != "prepare_repair_execution_readiness_gate"
    ):
        raise ValueError("repair readiness gate requires readiness gate next action")

    if _clean(feedback.get("source_noop_status")) != "completed":
        raise ValueError("repair readiness gate requires completed source noop")
    if int(feedback.get("source_noop_exit_code") or 0) != 0:
        raise ValueError("repair readiness gate requires zero source noop exit code")
    if not bool(feedback.get("source_noop_only")):
        raise ValueError("repair readiness gate requires noop-only source")
    if not bool(feedback.get("source_noop_stdout_marker_observed")):
        raise ValueError("repair readiness gate requires source noop marker")
    if not bool(feedback.get("source_execution_performed")):
        raise ValueError("repair readiness gate requires source noop execution")
    if not bool(feedback.get("source_subprocess_invoked")):
        raise ValueError("repair readiness gate requires source noop subprocess")

    if _clean(feedback.get("source_envelope_status")) != "prepared":
        raise ValueError("repair readiness gate requires prepared source envelope")
    if not bool(feedback.get("source_dry_run_only")):
        raise ValueError("repair readiness gate requires dry-run-only source envelope")
    if (
        _clean(feedback.get("source_repair_dry_run_mode"))
        != "repair_action_bundle_validation"
    ):
        raise ValueError("repair readiness gate requires repair validation source mode")
    if int(feedback.get("source_repair_dry_run_target_count") or 0) <= 0:
        raise ValueError("repair readiness gate requires source repair targets")
    if not bool(feedback.get("source_final_gate_ready_blocked")):
        raise ValueError("repair readiness gate requires ready-blocked source final gate")
    if not bool(feedback.get("source_transition_approved")):
        raise ValueError("repair readiness gate requires approved source transition")
    if not bool(feedback.get("operator_authorized")):
        raise ValueError("repair readiness gate requires operator_authorized feedback")

    if bool(feedback.get("source_repair_actions_executed")):
        raise ValueError("repair readiness gate rejects source repair actions executed")
    if bool(feedback.get("source_repair_bundle_executed")):
        raise ValueError("repair readiness gate rejects source repair bundle executed")
    if bool(feedback.get("source_repair_command_executed")):
        raise ValueError("repair readiness gate rejects source repair command executed")
    if bool(feedback.get("source_repair_execution_enabled")):
        raise ValueError("repair readiness gate rejects source repair execution enabled")
    if bool(feedback.get("source_repair_execution_performed")):
        raise ValueError("repair readiness gate rejects source repair execution performed")
    if bool(feedback.get("source_repair_subprocess_invoked")):
        raise ValueError("repair readiness gate rejects source repair subprocess invoked")

    if bool(feedback.get("feedback_execution_performed")):
        raise ValueError("repair readiness gate rejects feedback execution performed")
    if bool(feedback.get("feedback_subprocess_invoked")):
        raise ValueError("repair readiness gate rejects feedback subprocess invoked")
    if bool(feedback.get("ready_for_repair_execution")):
        raise ValueError("repair readiness gate rejects already ready feedback")
    if bool(feedback.get("would_execute")):
        raise ValueError("repair readiness gate rejects would_execute feedback")

    if bool(feedback.get("bundle_execution_enabled")):
        raise ValueError("repair readiness gate rejects bundle execution enabled")
    if bool(feedback.get("repair_execution_enabled")):
        raise ValueError("repair readiness gate rejects repair execution enabled")
    if bool(feedback.get("real_execution_enabled")):
        raise ValueError("repair readiness gate rejects real execution enabled")
    if bool(feedback.get("subprocess_enabled")):
        raise ValueError("repair readiness gate rejects subprocess enabled")
    if bool(feedback.get("repair_execution_performed")):
        raise ValueError("repair readiness gate rejects repair execution performed")
    if bool(feedback.get("repair_subprocess_invoked")):
        raise ValueError("repair readiness gate rejects repair subprocess invoked")
    if bool(feedback.get("execution_performed")):
        raise ValueError("repair readiness gate rejects feedback executed")
    if bool(feedback.get("subprocess_invoked")):
        raise ValueError("repair readiness gate rejects feedback subprocess invoked")


def build_real_execution_repair_readiness_gate_record(
    repair_noop_feedback: Mapping[str, Any],
    *,
    source: str = "real-execution-repair-readiness-gate",
) -> dict[str, Any]:
    _validate_feedback_preconditions(repair_noop_feedback)

    feedback_id = _clean(
        repair_noop_feedback.get("real_execution_repair_noop_feedback_id")
    )
    noop_result_id = _clean(
        repair_noop_feedback.get("real_execution_repair_noop_result_id")
    )
    envelope_id = _clean(
        repair_noop_feedback.get("real_execution_repair_dry_run_envelope_id")
    )
    final_gate_id = _clean(
        repair_noop_feedback.get("real_execution_repair_final_gate_id")
    )
    transition_id = _clean(
        repair_noop_feedback.get("real_execution_repair_approval_transition_id")
    )
    repair_approval_id = _clean(
        repair_noop_feedback.get("real_execution_repair_approval_id")
    )
    bundle_id = _clean(
        repair_noop_feedback.get("real_execution_read_only_repair_action_bundle_id")
    )
    repair_plan_id = _clean(
        repair_noop_feedback.get("real_execution_read_only_repair_plan_id")
    )
    rendered_command_id = _clean(repair_noop_feedback.get("rendered_command_id"))

    gate_id = _stable_id(
        "replay-retry-real-repair-readiness-gate",
        feedback_id,
        noop_result_id,
        envelope_id,
        final_gate_id,
        transition_id,
        repair_approval_id,
        bundle_id,
        repair_plan_id,
        rendered_command_id,
    )

    targets = _source_targets(repair_noop_feedback)
    target_count = int(
        repair_noop_feedback.get("source_repair_dry_run_target_count")
        or len(targets)
    )

    payload = {
        "real_execution_repair_readiness_gate_id": gate_id,
        "real_execution_repair_noop_feedback_id": feedback_id,
        "real_execution_repair_noop_result_id": noop_result_id,
        "real_execution_repair_dry_run_envelope_id": envelope_id,
        "real_execution_repair_final_gate_id": final_gate_id,
        "real_execution_repair_approval_transition_id": transition_id,
        "real_execution_repair_approval_id": repair_approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": _clean(
            repair_noop_feedback.get(
                "real_execution_read_only_repair_action_bundle_review_id"
            )
        ),
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_feedback_id")
        ),
        "real_execution_read_only_execution_result_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_execution_result_id")
        ),
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_noop_feedback.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_noop_feedback.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_noop_feedback.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_noop_feedback.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_noop_feedback.get("plan_id")),
        "proposal_id": _clean(repair_noop_feedback.get("proposal_id")),
        "approval_id": _clean(repair_noop_feedback.get("approval_id")),
        "timeout_profile": _clean(repair_noop_feedback.get("timeout_profile"))
        or "standard",
        "decision_mode": _clean(repair_noop_feedback.get("decision_mode"))
        or "manual",
        "gate_status": "ready_blocked",
        "repair_readiness_satisfied": True,
        "ready_for_guarded_repair_execution": True,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "blocking_reasons": [
            "guarded_repair_execution_requires_separate_pr",
        ],
        "recommended_next_action": "prepare_guarded_repair_execution_harness",
        "source_feedback_status": _clean(
            repair_noop_feedback.get("feedback_status")
        ),
        "source_repair_noop_verified": bool(
            repair_noop_feedback.get("repair_noop_verified")
        ),
        "source_repair_path_can_proceed": bool(
            repair_noop_feedback.get("repair_path_can_proceed")
        ),
        "source_repair_path_next_gate_allowed": bool(
            repair_noop_feedback.get("repair_path_next_gate_allowed")
        ),
        "source_noop_status": _clean(repair_noop_feedback.get("source_noop_status")),
        "source_noop_exit_code": repair_noop_feedback.get("source_noop_exit_code"),
        "source_noop_only": bool(repair_noop_feedback.get("source_noop_only")),
        "source_noop_stdout_marker_observed": bool(
            repair_noop_feedback.get("source_noop_stdout_marker_observed")
        ),
        "source_execution_performed": bool(
            repair_noop_feedback.get("source_execution_performed")
        ),
        "source_subprocess_invoked": bool(
            repair_noop_feedback.get("source_subprocess_invoked")
        ),
        "source_envelope_status": _clean(
            repair_noop_feedback.get("source_envelope_status")
        ),
        "source_dry_run_only": bool(repair_noop_feedback.get("source_dry_run_only")),
        "source_repair_dry_run_mode": _clean(
            repair_noop_feedback.get("source_repair_dry_run_mode")
        ),
        "source_repair_dry_run_target_count": target_count,
        "source_repair_dry_run_targets": targets,
        "source_final_gate_ready_blocked": bool(
            repair_noop_feedback.get("source_final_gate_ready_blocked")
        ),
        "source_transition_approved": bool(
            repair_noop_feedback.get("source_transition_approved")
        ),
        "operator_authorized": bool(repair_noop_feedback.get("operator_authorized")),
        "source_repair_actions_executed": bool(
            repair_noop_feedback.get("source_repair_actions_executed")
        ),
        "source_repair_bundle_executed": bool(
            repair_noop_feedback.get("source_repair_bundle_executed")
        ),
        "source_repair_command_executed": bool(
            repair_noop_feedback.get("source_repair_command_executed")
        ),
        "source_repair_execution_enabled": bool(
            repair_noop_feedback.get("source_repair_execution_enabled")
        ),
        "source_repair_execution_performed": bool(
            repair_noop_feedback.get("source_repair_execution_performed")
        ),
        "source_repair_subprocess_invoked": bool(
            repair_noop_feedback.get("source_repair_subprocess_invoked")
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
        "reason": "repair_execution_readiness_gate_recorded",
    }

    return {
        "type": REPAIR_READINESS_GATE_TYPE,
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
        and _clean(record.get("real_execution_repair_noop_feedback_id"))
        != feedback_id
    ):
        return False
    return True


def _find_existing_gate(
    records: list[Mapping[str, Any]],
    *,
    feedback_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_READINESS_GATE_TYPE:
            continue
        if (
            _clean(item.get("real_execution_repair_noop_feedback_id"))
            == feedback_id
        ):
            return item
    return None


async def build_real_execution_repair_readiness_gate_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-repair-readiness-gate"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    feedback_id = _clean(
        getattr(args, "real_execution_repair_noop_feedback_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    feedback_records = [
        item
        for item in records
        if item.get("type") == REPAIR_NOOP_FEEDBACK_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            feedback_id=feedback_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for feedback in feedback_records:
        current_feedback_id = _clean(
            feedback.get("real_execution_repair_noop_feedback_id")
        )
        if _find_existing_gate(records, feedback_id=current_feedback_id):
            logger.info(
                "Skipping duplicate repair readiness gate: feedback_id=%s",
                current_feedback_id,
            )
            continue

        record = build_real_execution_repair_readiness_gate_record(
            feedback,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published repair readiness gate: gate_id=%s status=%s "
            "satisfied=%s ready_for_guarded_repair_execution=%s "
            "repair_execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_repair_readiness_gate_id"),
            record.get("gate_status"),
            record.get("repair_readiness_satisfied"),
            record.get("ready_for_guarded_repair_execution"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info("Repair readiness gate builder completed: gates=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build repair execution readiness gate records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-repair-noop-feedback-id", default="")
    parser.add_argument("--source", default="real-execution-repair-readiness-gate")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_repair_readiness_gate_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Repair readiness gate builder completed: gates={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()