"""Build post-read-only execution feedback records.

This consumes guarded read-only execution results and publishes an immutable
feedback artifact for Overseer / experience-loop follow-up. It never executes a
command and never invokes subprocesses.
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

READ_ONLY_EXECUTION_RESULT_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_execution_result"
)

READ_ONLY_FEEDBACK_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_feedback"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _infer_feedback_status(status: str, exit_code: int | None) -> str:
    if status == "executed" and exit_code == 0:
        return "successful"
    if status == "failed":
        return "actionable"
    if status == "rejected":
        return "blocked"
    return "unknown"


def _infer_recommended_next_action(status: str, exit_code: int | None) -> str:
    if status == "executed" and exit_code == 0:
        return "promote_successful_read_only_execution_evidence"
    if status == "failed":
        return "investigate_failed_read_only_evidence_check"
    if status == "rejected":
        return "resolve_guarded_read_only_execution_rejection"
    return "inspect_unknown_read_only_execution_result"


def _extract_failure_hints(result: Mapping[str, Any]) -> list[str]:
    hints: list[str] = []

    status = _clean(result.get("status"))
    reason = _clean(result.get("reason"))
    exit_code = result.get("exit_code")
    stderr = _clean(result.get("stderr"))
    stdout = _clean(result.get("stdout"))
    validation_reasons = result.get("validation_reasons")

    if status:
        hints.append(f"source_status:{status}")
    if reason:
        hints.append(f"source_reason:{reason}")
    if exit_code is not None:
        hints.append(f"source_exit_code:{exit_code}")

    if isinstance(validation_reasons, list) and validation_reasons:
        hints.append("validation_reasons_present")
        for item in validation_reasons[:10]:
            clean_item = _clean(item)
            if clean_item:
                hints.append(f"validation_reason:{clean_item}")

    combined = f"{stdout}\n{stderr}".lower()
    known_markers = (
        "execution_published",
        "execution_completed",
        "evidence_published",
        "memory_record_published",
        "visibility_memory_summary_replay_evidence",
        "visibility_crdt_trail_complete",
        "scenario_seeded",
        "directive_seeded",
        "visibility_security_lifecycle_validation",
    )
    for marker in known_markers:
        if marker.lower() in combined:
            hints.append(f"observed_marker:{marker}")

    return sorted(set(hints))


def build_real_execution_read_only_feedback_record(
    execution_result: Mapping[str, Any],
    *,
    source: str = "real-execution-read-only-feedback",
) -> dict[str, Any]:
    result_id = _clean(
        execution_result.get("real_execution_read_only_execution_result_id")
    )
    readiness_gate_id = _clean(
        execution_result.get("real_execution_read_only_readiness_gate_id")
    )
    rendered_command_id = _clean(execution_result.get("rendered_command_id"))

    if not result_id:
        raise ValueError("real_execution_read_only_execution_result_id is required")
    if not readiness_gate_id:
        raise ValueError("real_execution_read_only_readiness_gate_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    source_status = _clean(execution_result.get("status")) or "unknown"
    source_reason = _clean(execution_result.get("reason")) or "unknown"
    raw_exit_code = execution_result.get("exit_code")
    source_exit_code = None if raw_exit_code is None else _safe_int(raw_exit_code)

    feedback_status = _infer_feedback_status(source_status, source_exit_code)
    recommended_next_action = _infer_recommended_next_action(
        source_status,
        source_exit_code,
    )
    failure_hints = _extract_failure_hints(execution_result)

    feedback_id = _stable_id(
        "replay-retry-real-read-only-feedback",
        result_id,
        readiness_gate_id,
        rendered_command_id,
        source_status,
        source_exit_code,
    )

    payload = {
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": result_id,
        "real_execution_read_only_readiness_gate_id": readiness_gate_id,
        "real_execution_read_only_approval_transition_id": _clean(
            execution_result.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            execution_result.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            execution_result.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            execution_result.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            execution_result.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            execution_result.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            execution_result.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(execution_result.get("plan_id")),
        "proposal_id": _clean(execution_result.get("proposal_id")),
        "approval_id": _clean(execution_result.get("approval_id")),
        "timeout_profile": _clean(execution_result.get("timeout_profile")) or "standard",
        "decision_mode": _clean(execution_result.get("decision_mode")) or "manual",
        "source_status": source_status,
        "source_reason": source_reason,
        "source_exit_code": source_exit_code,
        "feedback_status": feedback_status,
        "recommended_next_action": recommended_next_action,
        "failure_hints": failure_hints,
        "read_only_execution_was_observed": source_status in {"executed", "failed"},
        "read_only_execution_failed": source_status == "failed",
        "read_only_execution_succeeded": source_status == "executed"
        and source_exit_code == 0,
        "read_only_execution_rejected": source_status == "rejected",
        "operator_authorized": bool(execution_result.get("operator_authorized")),
        "allow_guarded_read_only_execution": bool(
            execution_result.get("allow_guarded_read_only_execution")
        ),
        "read_only_execution_enabled": bool(
            execution_result.get("read_only_execution_enabled")
        ),
        "real_execution_enabled": bool(execution_result.get("real_execution_enabled")),
        "source_subprocess_invoked": bool(execution_result.get("subprocess_invoked")),
        "source_execution_performed": bool(
            execution_result.get("execution_performed")
        ),
        "source_read_only_command_executed": bool(
            execution_result.get("read_only_command_executed")
        ),
        "source_rendered_command_executed": bool(
            execution_result.get("rendered_command_executed")
        ),
        "source_dry_run_command_executed": bool(
            execution_result.get("dry_run_envelope_command_executed")
        ),
        "feedback_execution_performed": False,
        "feedback_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "read_only_execution_feedback_recorded",
    }

    return {
        "type": READ_ONLY_FEEDBACK_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    execution_result_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        execution_result_id
        and _clean(record.get("real_execution_read_only_execution_result_id"))
        != execution_result_id
    ):
        return False
    return True


def _find_existing_feedback(
    records: list[Mapping[str, Any]],
    *,
    execution_result_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != READ_ONLY_FEEDBACK_TYPE:
            continue
        if (
            _clean(item.get("real_execution_read_only_execution_result_id"))
            == execution_result_id
        ):
            return item
    return None


async def build_real_execution_read_only_feedback_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-read-only-feedback"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    execution_result_id = _clean(
        getattr(args, "real_execution_read_only_execution_result_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    execution_results = [
        item
        for item in records
        if item.get("type") == READ_ONLY_EXECUTION_RESULT_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            execution_result_id=execution_result_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for execution_result in execution_results:
        current_result_id = _clean(
            execution_result.get("real_execution_read_only_execution_result_id")
        )
        if _find_existing_feedback(
            records,
            execution_result_id=current_result_id,
        ):
            logger.info(
                "Skipping duplicate read-only feedback: execution_result_id=%s",
                current_result_id,
            )
            continue

        record = build_real_execution_read_only_feedback_record(
            execution_result,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only execution feedback: feedback_id=%s status=%s next_action=%s",
            record.get("real_execution_read_only_feedback_id"),
            record.get("feedback_status"),
            record.get("recommended_next_action"),
        )

    logger.info("Read-only execution feedback builder completed: feedback=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build post-read-only execution feedback records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-execution-result-id", default="")
    parser.add_argument("--source", default="real-execution-read-only-feedback")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_feedback_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Read-only execution feedback builder completed: feedback={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()