"""Build repair noop feedback records.

Consumes a completed repair noop result and emits a feedback artifact deciding
whether the repair path can proceed to the next guarded gate. This feedback
never executes repair actions, never invokes subprocesses, and never enables
repair execution.
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

REPAIR_NOOP_RESULT_TYPE = "replay_lifecycle_retry_real_execution_repair_noop_result"

REPAIR_NOOP_FEEDBACK_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_noop_feedback"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_targets(noop_result: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(noop_result.get("source_repair_dry_run_targets"))
            if _clean(item)
        }
    )


def _validate_noop_result(noop_result: Mapping[str, Any]) -> None:
    result_id = _clean(noop_result.get("real_execution_repair_noop_result_id"))
    envelope_id = _clean(
        noop_result.get("real_execution_repair_dry_run_envelope_id")
    )
    final_gate_id = _clean(noop_result.get("real_execution_repair_final_gate_id"))
    rendered_command_id = _clean(noop_result.get("rendered_command_id"))

    if not result_id:
        raise ValueError("real_execution_repair_noop_result_id is required")
    if not envelope_id:
        raise ValueError("real_execution_repair_dry_run_envelope_id is required")
    if not final_gate_id:
        raise ValueError("real_execution_repair_final_gate_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    if _clean(noop_result.get("repair_noop_status")) != "completed":
        raise ValueError("repair noop feedback requires completed noop result")
    if int(noop_result.get("exit_code") or 0) != 0:
        raise ValueError("repair noop feedback requires zero exit code")
    if not bool(noop_result.get("noop_only")):
        raise ValueError("repair noop feedback requires noop_only result")
    if not bool(noop_result.get("noop_stdout_marker_observed")):
        raise ValueError("repair noop feedback requires stdout marker")
    if _clean(noop_result.get("source_envelope_status")) != "prepared":
        raise ValueError("repair noop feedback requires prepared source envelope")
    if not bool(noop_result.get("source_dry_run_only")):
        raise ValueError("repair noop feedback requires dry-run-only source envelope")
    if (
        _clean(noop_result.get("source_repair_dry_run_mode"))
        != "repair_action_bundle_validation"
    ):
        raise ValueError("repair noop feedback requires repair validation source mode")
    if not bool(noop_result.get("source_final_gate_ready_blocked")):
        raise ValueError("repair noop feedback requires ready-blocked source gate")
    if not bool(noop_result.get("source_transition_approved")):
        raise ValueError("repair noop feedback requires approved source transition")
    if not bool(noop_result.get("operator_authorized")):
        raise ValueError("repair noop feedback requires operator_authorized result")

    if int(noop_result.get("source_repair_dry_run_target_count") or 0) <= 0:
        raise ValueError("repair noop feedback requires source repair targets")

    if bool(noop_result.get("repair_actions_executed")):
        raise ValueError("repair noop feedback rejects repair_actions_executed result")
    if bool(noop_result.get("repair_bundle_executed")):
        raise ValueError("repair noop feedback rejects repair_bundle_executed result")
    if bool(noop_result.get("repair_command_executed")):
        raise ValueError("repair noop feedback rejects repair_command_executed result")
    if bool(noop_result.get("rendered_command_executed")):
        raise ValueError("repair noop feedback rejects rendered_command_executed result")
    if bool(noop_result.get("dry_run_command_executed")):
        raise ValueError("repair noop feedback rejects dry_run_command_executed result")
    if bool(noop_result.get("repair_execution_enabled")):
        raise ValueError("repair noop feedback rejects repair_execution_enabled result")
    if bool(noop_result.get("real_execution_enabled")):
        raise ValueError("repair noop feedback rejects real_execution_enabled result")
    if bool(noop_result.get("subprocess_enabled")):
        raise ValueError("repair noop feedback rejects subprocess_enabled result")
    if bool(noop_result.get("repair_execution_performed")):
        raise ValueError("repair noop feedback rejects repair_execution_performed result")
    if bool(noop_result.get("repair_subprocess_invoked")):
        raise ValueError("repair noop feedback rejects repair_subprocess_invoked result")

    if not bool(noop_result.get("execution_performed")):
        raise ValueError("repair noop feedback requires controlled noop execution")
    if not bool(noop_result.get("subprocess_invoked")):
        raise ValueError("repair noop feedback requires controlled noop subprocess")


def build_real_execution_repair_noop_feedback_record(
    repair_noop_result: Mapping[str, Any],
    *,
    source: str = "real-execution-repair-noop-feedback",
) -> dict[str, Any]:
    _validate_noop_result(repair_noop_result)

    noop_result_id = _clean(
        repair_noop_result.get("real_execution_repair_noop_result_id")
    )
    envelope_id = _clean(
        repair_noop_result.get("real_execution_repair_dry_run_envelope_id")
    )
    final_gate_id = _clean(
        repair_noop_result.get("real_execution_repair_final_gate_id")
    )
    transition_id = _clean(
        repair_noop_result.get("real_execution_repair_approval_transition_id")
    )
    repair_approval_id = _clean(
        repair_noop_result.get("real_execution_repair_approval_id")
    )
    bundle_id = _clean(
        repair_noop_result.get("real_execution_read_only_repair_action_bundle_id")
    )
    repair_plan_id = _clean(
        repair_noop_result.get("real_execution_read_only_repair_plan_id")
    )
    rendered_command_id = _clean(repair_noop_result.get("rendered_command_id"))

    feedback_id = _stable_id(
        "replay-retry-real-repair-noop-feedback",
        noop_result_id,
        envelope_id,
        final_gate_id,
        transition_id,
        repair_approval_id,
        bundle_id,
        repair_plan_id,
        rendered_command_id,
    )

    targets = _source_targets(repair_noop_result)
    source_target_count = int(
        repair_noop_result.get("source_repair_dry_run_target_count") or len(targets)
    )

    repair_path_can_proceed = (
        _clean(repair_noop_result.get("repair_noop_status")) == "completed"
        and int(repair_noop_result.get("exit_code") or 0) == 0
        and bool(repair_noop_result.get("noop_only"))
        and bool(repair_noop_result.get("noop_stdout_marker_observed"))
        and bool(repair_noop_result.get("operator_authorized"))
        and source_target_count > 0
    )

    feedback_status = "actionable" if repair_path_can_proceed else "blocked"
    next_action = (
        "prepare_repair_execution_readiness_gate"
        if repair_path_can_proceed
        else "investigate_repair_noop_feedback_blocker"
    )

    payload = {
        "real_execution_repair_noop_feedback_id": feedback_id,
        "real_execution_repair_noop_result_id": noop_result_id,
        "real_execution_repair_dry_run_envelope_id": envelope_id,
        "real_execution_repair_final_gate_id": final_gate_id,
        "real_execution_repair_approval_transition_id": transition_id,
        "real_execution_repair_approval_id": repair_approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": _clean(
            repair_noop_result.get(
                "real_execution_read_only_repair_action_bundle_review_id"
            )
        ),
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": _clean(
            repair_noop_result.get("real_execution_read_only_feedback_id")
        ),
        "real_execution_read_only_execution_result_id": _clean(
            repair_noop_result.get("real_execution_read_only_execution_result_id")
        ),
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_noop_result.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_noop_result.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_noop_result.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_noop_result.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_noop_result.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_noop_result.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_noop_result.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_noop_result.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_noop_result.get("plan_id")),
        "proposal_id": _clean(repair_noop_result.get("proposal_id")),
        "approval_id": _clean(repair_noop_result.get("approval_id")),
        "timeout_profile": _clean(repair_noop_result.get("timeout_profile"))
        or "standard",
        "decision_mode": _clean(repair_noop_result.get("decision_mode")) or "manual",
        "feedback_status": feedback_status,
        "repair_noop_verified": repair_path_can_proceed,
        "repair_path_can_proceed": repair_path_can_proceed,
        "repair_path_next_gate_allowed": repair_path_can_proceed,
        "recommended_next_action": next_action,
        "source_noop_status": _clean(repair_noop_result.get("repair_noop_status")),
        "source_noop_exit_code": repair_noop_result.get("exit_code"),
        "source_noop_only": bool(repair_noop_result.get("noop_only")),
        "source_noop_stdout_marker_observed": bool(
            repair_noop_result.get("noop_stdout_marker_observed")
        ),
        "source_execution_performed": bool(
            repair_noop_result.get("execution_performed")
        ),
        "source_subprocess_invoked": bool(
            repair_noop_result.get("subprocess_invoked")
        ),
        "source_envelope_status": _clean(
            repair_noop_result.get("source_envelope_status")
        )
        or "unknown",
        "source_dry_run_only": bool(repair_noop_result.get("source_dry_run_only")),
        "source_repair_dry_run_mode": _clean(
            repair_noop_result.get("source_repair_dry_run_mode")
        )
        or "unknown",
        "source_repair_dry_run_target_count": source_target_count,
        "source_repair_dry_run_targets": targets,
        "source_final_gate_ready_blocked": bool(
            repair_noop_result.get("source_final_gate_ready_blocked")
        ),
        "source_transition_approved": bool(
            repair_noop_result.get("source_transition_approved")
        ),
        "operator_authorized": bool(repair_noop_result.get("operator_authorized")),
        "source_repair_actions_executed": bool(
            repair_noop_result.get("repair_actions_executed")
        ),
        "source_repair_bundle_executed": bool(
            repair_noop_result.get("repair_bundle_executed")
        ),
        "source_repair_command_executed": bool(
            repair_noop_result.get("repair_command_executed")
        ),
        "source_repair_execution_enabled": bool(
            repair_noop_result.get("repair_execution_enabled")
        ),
        "source_repair_execution_performed": bool(
            repair_noop_result.get("repair_execution_performed")
        ),
        "source_repair_subprocess_invoked": bool(
            repair_noop_result.get("repair_subprocess_invoked")
        ),
        "feedback_execution_performed": False,
        "feedback_subprocess_invoked": False,
        "ready_for_repair_execution": False,
        "would_execute": False,
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
        "reason": "repair_execution_noop_feedback_recorded",
    }

    return {
        "type": REPAIR_NOOP_FEEDBACK_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    noop_result_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        noop_result_id
        and _clean(record.get("real_execution_repair_noop_result_id"))
        != noop_result_id
    ):
        return False
    return True


def _find_existing_feedback(
    records: list[Mapping[str, Any]],
    *,
    noop_result_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_NOOP_FEEDBACK_TYPE:
            continue
        if (
            _clean(item.get("real_execution_repair_noop_result_id"))
            == noop_result_id
        ):
            return item
    return None


async def build_real_execution_repair_noop_feedback_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-repair-noop-feedback"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    noop_result_id = _clean(getattr(args, "real_execution_repair_noop_result_id", ""))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    noop_results = [
        item
        for item in records
        if item.get("type") == REPAIR_NOOP_RESULT_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            noop_result_id=noop_result_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for noop_result in noop_results:
        current_result_id = _clean(
            noop_result.get("real_execution_repair_noop_result_id")
        )
        if _find_existing_feedback(records, noop_result_id=current_result_id):
            logger.info(
                "Skipping duplicate repair noop feedback: noop_result_id=%s",
                current_result_id,
            )
            continue

        record = build_real_execution_repair_noop_feedback_record(
            noop_result,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published repair noop feedback: feedback_id=%s status=%s "
            "repair_path_can_proceed=%s repair_execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_repair_noop_feedback_id"),
            record.get("feedback_status"),
            record.get("repair_path_can_proceed"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info("Repair noop feedback builder completed: feedback=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build repair noop feedback records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-repair-noop-result-id", default="")
    parser.add_argument("--source", default="real-execution-repair-noop-feedback")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_repair_noop_feedback_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Repair noop feedback builder completed: feedback={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()