"""Run guarded repair execution.

Consumes a ready-blocked repair readiness gate. By default this runner is
fail-closed and publishes a rejected result without executing anything.

When --allow-guarded-repair-execution is provided, it executes only a controlled
repair action bundle harness subprocess. It must never execute the original
rendered command and must never enable arbitrary real execution.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
import sys
import time
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

REPAIR_READINESS_GATE_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_readiness_gate"
)

REPAIR_EXECUTION_RESULT_TYPE = (
    "replay_lifecycle_retry_guarded_repair_execution_result"
)

GUARDED_REPAIR_MARKER = "guarded-repair-execution-ok"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _repair_targets(gate: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(gate.get("source_repair_dry_run_targets"))
            if _clean(item)
        }
    )


def _validate_readiness_gate(gate: Mapping[str, Any]) -> None:
    gate_id = _clean(gate.get("real_execution_repair_readiness_gate_id"))
    feedback_id = _clean(gate.get("real_execution_repair_noop_feedback_id"))
    noop_result_id = _clean(gate.get("real_execution_repair_noop_result_id"))
    envelope_id = _clean(gate.get("real_execution_repair_dry_run_envelope_id"))
    final_gate_id = _clean(gate.get("real_execution_repair_final_gate_id"))
    rendered_command_id = _clean(gate.get("rendered_command_id"))

    if not gate_id:
        raise ValueError("real_execution_repair_readiness_gate_id is required")
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

    if _clean(gate.get("gate_status")) != "ready_blocked":
        raise ValueError("guarded repair execution requires ready_blocked gate")
    if not bool(gate.get("repair_readiness_satisfied")):
        raise ValueError("guarded repair execution requires satisfied readiness")
    if not bool(gate.get("ready_for_guarded_repair_execution")):
        raise ValueError("guarded repair execution requires guarded readiness")
    if bool(gate.get("ready_for_repair_execution")):
        raise ValueError("guarded repair execution rejects ready_for_repair_execution")
    if bool(gate.get("would_execute")):
        raise ValueError("guarded repair execution rejects would_execute gate")

    blocking_reasons = gate.get("blocking_reasons")
    if not isinstance(blocking_reasons, list):
        blocking_reasons = []
    if "guarded_repair_execution_requires_separate_pr" not in blocking_reasons:
        raise ValueError("guarded repair execution requires separate PR blocker")

    if _clean(gate.get("recommended_next_action")) != "prepare_guarded_repair_execution_harness":
        raise ValueError("guarded repair execution requires harness next action")

    if _clean(gate.get("source_feedback_status")) != "actionable":
        raise ValueError("guarded repair execution requires actionable source feedback")
    if not bool(gate.get("source_repair_noop_verified")):
        raise ValueError("guarded repair execution requires verified source noop")
    if not bool(gate.get("source_repair_path_can_proceed")):
        raise ValueError("guarded repair execution requires source path can proceed")
    if not bool(gate.get("source_repair_path_next_gate_allowed")):
        raise ValueError("guarded repair execution requires source next gate allowed")

    if _clean(gate.get("source_noop_status")) != "completed":
        raise ValueError("guarded repair execution requires completed source noop")
    if int(gate.get("source_noop_exit_code") or 0) != 0:
        raise ValueError("guarded repair execution requires zero source noop exit code")
    if not bool(gate.get("source_noop_only")):
        raise ValueError("guarded repair execution requires noop-only source")
    if not bool(gate.get("source_noop_stdout_marker_observed")):
        raise ValueError("guarded repair execution requires source noop marker")
    if not bool(gate.get("source_execution_performed")):
        raise ValueError("guarded repair execution requires source noop execution")
    if not bool(gate.get("source_subprocess_invoked")):
        raise ValueError("guarded repair execution requires source noop subprocess")

    if _clean(gate.get("source_envelope_status")) != "prepared":
        raise ValueError("guarded repair execution requires prepared source envelope")
    if not bool(gate.get("source_dry_run_only")):
        raise ValueError("guarded repair execution requires dry-run-only source envelope")
    if _clean(gate.get("source_repair_dry_run_mode")) != "repair_action_bundle_validation":
        raise ValueError("guarded repair execution requires repair validation source mode")
    if int(gate.get("source_repair_dry_run_target_count") or 0) <= 0:
        raise ValueError("guarded repair execution requires source repair targets")
    if not bool(gate.get("source_final_gate_ready_blocked")):
        raise ValueError("guarded repair execution requires ready-blocked source final gate")
    if not bool(gate.get("source_transition_approved")):
        raise ValueError("guarded repair execution requires approved source transition")
    if not bool(gate.get("operator_authorized")):
        raise ValueError("guarded repair execution requires operator_authorized gate")

    if bool(gate.get("source_repair_actions_executed")):
        raise ValueError("guarded repair execution rejects source repair actions executed")
    if bool(gate.get("source_repair_bundle_executed")):
        raise ValueError("guarded repair execution rejects source repair bundle executed")
    if bool(gate.get("source_repair_command_executed")):
        raise ValueError("guarded repair execution rejects source repair command executed")
    if bool(gate.get("source_repair_execution_enabled")):
        raise ValueError("guarded repair execution rejects source repair execution enabled")
    if bool(gate.get("source_repair_execution_performed")):
        raise ValueError("guarded repair execution rejects source repair execution performed")
    if bool(gate.get("source_repair_subprocess_invoked")):
        raise ValueError("guarded repair execution rejects source repair subprocess invoked")

    if bool(gate.get("repair_execution_enabled")):
        raise ValueError("guarded repair execution rejects repair_execution_enabled gate")
    if bool(gate.get("real_execution_enabled")):
        raise ValueError("guarded repair execution rejects real_execution_enabled gate")
    if bool(gate.get("subprocess_enabled")):
        raise ValueError("guarded repair execution rejects subprocess_enabled gate")
    if bool(gate.get("repair_execution_performed")):
        raise ValueError("guarded repair execution rejects repair_execution_performed gate")
    if bool(gate.get("repair_subprocess_invoked")):
        raise ValueError("guarded repair execution rejects repair_subprocess_invoked gate")
    if bool(gate.get("execution_performed")):
        raise ValueError("guarded repair execution rejects executed gate")
    if bool(gate.get("subprocess_invoked")):
        raise ValueError("guarded repair execution rejects subprocess-invoked gate")


def _run_guarded_repair_subprocess(
    *,
    targets: list[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    argv = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "targets=sys.argv[1:]; "
            f"print({GUARDED_REPAIR_MARKER!r}); "
            "print(json.dumps({'status':'completed','targets':targets}, sort_keys=True))"
        ),
        *targets,
    ]

    started = time.monotonic()
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    duration = time.monotonic() - started

    return {
        "repair_argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": round(duration, 6),
    }


def build_guarded_repair_execution_result_record(
    repair_readiness_gate: Mapping[str, Any],
    *,
    allow_guarded_repair_execution: bool,
    subprocess_result: Mapping[str, Any] | None = None,
    source: str = "guarded-repair-execution",
) -> dict[str, Any]:
    _validate_readiness_gate(repair_readiness_gate)

    gate_id = _clean(
        repair_readiness_gate.get("real_execution_repair_readiness_gate_id")
    )
    feedback_id = _clean(
        repair_readiness_gate.get("real_execution_repair_noop_feedback_id")
    )
    noop_result_id = _clean(
        repair_readiness_gate.get("real_execution_repair_noop_result_id")
    )
    envelope_id = _clean(
        repair_readiness_gate.get("real_execution_repair_dry_run_envelope_id")
    )
    final_gate_id = _clean(
        repair_readiness_gate.get("real_execution_repair_final_gate_id")
    )
    transition_id = _clean(
        repair_readiness_gate.get("real_execution_repair_approval_transition_id")
    )
    repair_approval_id = _clean(
        repair_readiness_gate.get("real_execution_repair_approval_id")
    )
    rendered_command_id = _clean(repair_readiness_gate.get("rendered_command_id"))

    result_id = _stable_id(
        "replay-retry-guarded-repair-execution-result",
        gate_id,
        feedback_id,
        noop_result_id,
        envelope_id,
        final_gate_id,
        transition_id,
        repair_approval_id,
        rendered_command_id,
        str(bool(allow_guarded_repair_execution)).lower(),
    )

    targets = _repair_targets(repair_readiness_gate)
    target_count = int(
        repair_readiness_gate.get("source_repair_dry_run_target_count")
        or len(targets)
    )

    subprocess_result = subprocess_result if isinstance(subprocess_result, Mapping) else {}
    stdout = str(subprocess_result.get("stdout") or "")
    stderr = str(subprocess_result.get("stderr") or "")
    exit_code = (
        int(subprocess_result.get("exit_code"))
        if "exit_code" in subprocess_result
        else None
    )
    duration_seconds = float(subprocess_result.get("duration_seconds") or 0.0)
    repair_argv = _safe_list(subprocess_result.get("repair_argv"))

    marker_observed = GUARDED_REPAIR_MARKER in stdout

    if not allow_guarded_repair_execution:
        status = "rejected"
        reason = "guarded_repair_execution_not_allowed"
        next_action = "authorize_guarded_repair_execution"
        repair_execution_enabled = False
        subprocess_enabled = False
        execution_performed = False
        subprocess_invoked = False
        repair_actions_executed = False
        repair_bundle_executed = False
        repair_command_executed = False
    else:
        repair_execution_enabled = True
        subprocess_enabled = True
        execution_performed = True
        subprocess_invoked = True
        succeeded = exit_code == 0 and marker_observed
        status = "succeeded" if succeeded else "failed"
        reason = (
            "guarded_repair_execution_succeeded"
            if succeeded
            else "guarded_repair_execution_failed"
        )
        next_action = (
            "run_post_repair_evidence_check"
            if succeeded
            else "investigate_guarded_repair_execution_failure"
        )
        repair_actions_executed = succeeded
        repair_bundle_executed = succeeded
        repair_command_executed = succeeded

    repair_action_results = [
        {
            "target": target,
            "status": "completed" if repair_actions_executed else "not_executed",
        }
        for target in targets
    ]

    payload = {
        "guarded_repair_execution_result_id": result_id,
        "real_execution_repair_readiness_gate_id": gate_id,
        "real_execution_repair_noop_feedback_id": feedback_id,
        "real_execution_repair_noop_result_id": noop_result_id,
        "real_execution_repair_dry_run_envelope_id": envelope_id,
        "real_execution_repair_final_gate_id": final_gate_id,
        "real_execution_repair_approval_transition_id": transition_id,
        "real_execution_repair_approval_id": repair_approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": _clean(
            repair_readiness_gate.get(
                "real_execution_read_only_repair_action_bundle_review_id"
            )
        ),
        "real_execution_read_only_repair_action_bundle_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_repair_action_bundle_id")
        ),
        "real_execution_read_only_repair_plan_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_repair_plan_id")
        ),
        "real_execution_read_only_feedback_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_feedback_id")
        ),
        "real_execution_read_only_execution_result_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_execution_result_id")
        ),
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_readiness_gate.get(
                "real_execution_read_only_approval_transition_id"
            )
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_readiness_gate.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_readiness_gate.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_readiness_gate.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_readiness_gate.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_readiness_gate.get("plan_id")),
        "proposal_id": _clean(repair_readiness_gate.get("proposal_id")),
        "approval_id": _clean(repair_readiness_gate.get("approval_id")),
        "timeout_profile": _clean(repair_readiness_gate.get("timeout_profile"))
        or "standard",
        "decision_mode": _clean(repair_readiness_gate.get("decision_mode"))
        or "manual",
        "repair_execution_status": status,
        "repair_execution_allowed": bool(allow_guarded_repair_execution),
        "guarded_repair_execution": True,
        "guarded_repair_marker": GUARDED_REPAIR_MARKER,
        "guarded_repair_marker_observed": marker_observed,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration_seconds,
        "repair_argv": repair_argv,
        "source_gate_status": _clean(repair_readiness_gate.get("gate_status")),
        "source_repair_readiness_satisfied": bool(
            repair_readiness_gate.get("repair_readiness_satisfied")
        ),
        "source_ready_for_guarded_repair_execution": bool(
            repair_readiness_gate.get("ready_for_guarded_repair_execution")
        ),
        "source_ready_for_repair_execution": bool(
            repair_readiness_gate.get("ready_for_repair_execution")
        ),
        "source_would_execute": bool(repair_readiness_gate.get("would_execute")),
        "source_feedback_status": _clean(
            repair_readiness_gate.get("source_feedback_status")
        ),
        "source_repair_noop_verified": bool(
            repair_readiness_gate.get("source_repair_noop_verified")
        ),
        "source_repair_path_can_proceed": bool(
            repair_readiness_gate.get("source_repair_path_can_proceed")
        ),
        "source_repair_path_next_gate_allowed": bool(
            repair_readiness_gate.get("source_repair_path_next_gate_allowed")
        ),
        "source_noop_status": _clean(repair_readiness_gate.get("source_noop_status")),
        "source_noop_exit_code": repair_readiness_gate.get("source_noop_exit_code"),
        "source_execution_performed": bool(
            repair_readiness_gate.get("source_execution_performed")
        ),
        "source_subprocess_invoked": bool(
            repair_readiness_gate.get("source_subprocess_invoked")
        ),
        "source_repair_dry_run_target_count": target_count,
        "source_repair_dry_run_targets": targets,
        "operator_authorized": bool(repair_readiness_gate.get("operator_authorized")),
        "repair_action_results": repair_action_results,
        "repair_action_target_count": len(targets),
        "repair_actions_executed": repair_actions_executed,
        "repair_bundle_executed": repair_bundle_executed,
        "repair_command_executed": repair_command_executed,
        "rendered_command_executed": False,
        "dry_run_command_executed": False,
        "bundle_execution_enabled": repair_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": False,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": repair_bundle_executed,
        "bundle_subprocess_invoked": subprocess_invoked,
        "repair_execution_performed": repair_actions_executed,
        "repair_subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "recommended_next_action": next_action,
        "reason": reason,
    }

    return {
        "type": REPAIR_EXECUTION_RESULT_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    gate_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        gate_id
        and _clean(record.get("real_execution_repair_readiness_gate_id")) != gate_id
    ):
        return False
    return True


def _find_existing_result(
    records: list[Mapping[str, Any]],
    *,
    gate_id: str,
    allowed: bool,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_EXECUTION_RESULT_TYPE:
            continue
        if _clean(item.get("real_execution_repair_readiness_gate_id")) != gate_id:
            continue
        if bool(item.get("repair_execution_allowed")) == bool(allowed):
            return item
    return None


async def run_guarded_repair_execution_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "guarded-repair-execution"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    gate_id = _clean(getattr(args, "real_execution_repair_readiness_gate_id", ""))
    allow_guarded_repair_execution = bool(
        getattr(args, "allow_guarded_repair_execution", False)
    )
    timeout_seconds = int(getattr(args, "timeout_seconds", 10) or 10)

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    gates = [
        item
        for item in records
        if item.get("type") == REPAIR_READINESS_GATE_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            gate_id=gate_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for gate in gates:
        current_gate_id = _clean(gate.get("real_execution_repair_readiness_gate_id"))
        if _find_existing_result(
            records,
            gate_id=current_gate_id,
            allowed=allow_guarded_repair_execution,
        ):
            logger.info(
                "Skipping duplicate guarded repair execution result: gate_id=%s allowed=%s",
                current_gate_id,
                allow_guarded_repair_execution,
            )
            continue

        subprocess_result: Mapping[str, Any] | None = None
        if allow_guarded_repair_execution:
            subprocess_result = _run_guarded_repair_subprocess(
                targets=_repair_targets(gate),
                timeout_seconds=timeout_seconds,
            )

        record = build_guarded_repair_execution_result_record(
            gate,
            allow_guarded_repair_execution=allow_guarded_repair_execution,
            subprocess_result=subprocess_result,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published guarded repair execution result: result_id=%s status=%s "
            "allowed=%s repair_actions_executed=%s repair_execution_enabled=%s "
            "subprocess_invoked=%s",
            record.get("guarded_repair_execution_result_id"),
            record.get("repair_execution_status"),
            record.get("repair_execution_allowed"),
            record.get("repair_actions_executed"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info("Guarded repair execution completed: results=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run guarded repair execution.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-repair-readiness-gate-id", default="")
    parser.add_argument("--allow-guarded-repair-execution", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--source", default="guarded-repair-execution")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await run_guarded_repair_execution_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Guarded repair execution completed: results={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()