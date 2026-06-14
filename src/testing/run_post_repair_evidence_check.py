"""Run post-repair evidence verification.

Consumes a succeeded guarded repair execution result and emits a post-repair
evidence check record. This verifies the guarded repair outcome but does not
perform additional repair execution and does not enable arbitrary real execution.
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

GUARDED_REPAIR_EXECUTION_RESULT_TYPE = (
    "replay_lifecycle_retry_guarded_repair_execution_result"
)

POST_REPAIR_EVIDENCE_CHECK_TYPE = (
    "replay_lifecycle_retry_post_repair_evidence_check"
)

POST_REPAIR_EVIDENCE_MARKER = "post-repair-evidence-ok"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _repair_targets(result: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(result.get("source_repair_dry_run_targets"))
            if _clean(item)
        }
    )


def _repair_action_results(result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        item
        for item in _safe_list(result.get("repair_action_results"))
        if isinstance(item, Mapping)
    ]


def _completed_repair_targets(result: Mapping[str, Any]) -> list[str]:
    completed: set[str] = set()
    for item in _repair_action_results(result):
        if _clean(item.get("status")) == "completed":
            target = _clean(item.get("target"))
            if target:
                completed.add(target)
    return sorted(completed)


def _validate_guarded_repair_execution_result(result: Mapping[str, Any]) -> None:
    result_id = _clean(result.get("guarded_repair_execution_result_id"))
    gate_id = _clean(result.get("real_execution_repair_readiness_gate_id"))
    feedback_id = _clean(result.get("real_execution_repair_noop_feedback_id"))
    noop_result_id = _clean(result.get("real_execution_repair_noop_result_id"))
    envelope_id = _clean(result.get("real_execution_repair_dry_run_envelope_id"))
    rendered_command_id = _clean(result.get("rendered_command_id"))

    if not result_id:
        raise ValueError("guarded_repair_execution_result_id is required")
    if not gate_id:
        raise ValueError("real_execution_repair_readiness_gate_id is required")
    if not feedback_id:
        raise ValueError("real_execution_repair_noop_feedback_id is required")
    if not noop_result_id:
        raise ValueError("real_execution_repair_noop_result_id is required")
    if not envelope_id:
        raise ValueError("real_execution_repair_dry_run_envelope_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    if _clean(result.get("repair_execution_status")) != "succeeded":
        raise ValueError("post-repair evidence check requires succeeded repair result")
    if not bool(result.get("repair_execution_allowed")):
        raise ValueError("post-repair evidence check requires allowed repair result")
    if not bool(result.get("guarded_repair_execution")):
        raise ValueError("post-repair evidence check requires guarded repair execution")
    if not bool(result.get("guarded_repair_marker_observed")):
        raise ValueError("post-repair evidence check requires guarded repair marker")
    if int(result.get("exit_code") or 0) != 0:
        raise ValueError("post-repair evidence check requires zero repair exit code")

    if _clean(result.get("recommended_next_action")) != "run_post_repair_evidence_check":
        raise ValueError("post-repair evidence check requires post-repair next action")

    if _clean(result.get("source_gate_status")) != "ready_blocked":
        raise ValueError("post-repair evidence check requires ready-blocked source gate")
    if not bool(result.get("source_repair_readiness_satisfied")):
        raise ValueError("post-repair evidence check requires satisfied source readiness")
    if not bool(result.get("source_ready_for_guarded_repair_execution")):
        raise ValueError("post-repair evidence check requires guarded-ready source")
    if bool(result.get("source_ready_for_repair_execution")):
        raise ValueError("post-repair evidence check rejects source ready_for_repair")
    if bool(result.get("source_would_execute")):
        raise ValueError("post-repair evidence check rejects source would_execute")
    if _clean(result.get("source_feedback_status")) != "actionable":
        raise ValueError("post-repair evidence check requires actionable source feedback")
    if _clean(result.get("source_noop_status")) != "completed":
        raise ValueError("post-repair evidence check requires completed source noop")
    if int(result.get("source_noop_exit_code") or 0) != 0:
        raise ValueError("post-repair evidence check requires zero source noop exit code")
    if not bool(result.get("source_execution_performed")):
        raise ValueError("post-repair evidence check requires source noop execution")
    if not bool(result.get("source_subprocess_invoked")):
        raise ValueError("post-repair evidence check requires source noop subprocess")
    if not bool(result.get("operator_authorized")):
        raise ValueError("post-repair evidence check requires operator_authorized")

    expected_count = int(result.get("repair_action_target_count") or 0)
    targets = _repair_targets(result)
    completed_targets = _completed_repair_targets(result)

    if expected_count <= 0:
        raise ValueError("post-repair evidence check requires repair targets")
    if len(targets) != expected_count:
        raise ValueError("post-repair evidence check requires target count match")
    if completed_targets != targets:
        raise ValueError("post-repair evidence check requires completed repair targets")

    if not bool(result.get("repair_actions_executed")):
        raise ValueError("post-repair evidence check requires repair actions executed")
    if not bool(result.get("repair_bundle_executed")):
        raise ValueError("post-repair evidence check requires repair bundle executed")
    if not bool(result.get("repair_command_executed")):
        raise ValueError("post-repair evidence check requires repair command executed")
    if bool(result.get("rendered_command_executed")):
        raise ValueError("post-repair evidence check rejects rendered command execution")
    if bool(result.get("dry_run_command_executed")):
        raise ValueError("post-repair evidence check rejects dry-run command execution")
    if not bool(result.get("repair_execution_enabled")):
        raise ValueError("post-repair evidence check requires repair execution enabled")
    if bool(result.get("real_execution_enabled")):
        raise ValueError("post-repair evidence check rejects real execution enabled")
    if not bool(result.get("subprocess_enabled")):
        raise ValueError("post-repair evidence check requires subprocess enabled")
    if not bool(result.get("repair_execution_performed")):
        raise ValueError("post-repair evidence check requires repair execution performed")
    if not bool(result.get("repair_subprocess_invoked")):
        raise ValueError("post-repair evidence check requires repair subprocess invoked")
    if not bool(result.get("execution_performed")):
        raise ValueError("post-repair evidence check requires execution performed")
    if not bool(result.get("subprocess_invoked")):
        raise ValueError("post-repair evidence check requires subprocess invoked")


def _run_post_repair_verifier(
    *,
    targets: list[str],
    completed_targets: list[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    payload = {
        "targets": targets,
        "completed_targets": completed_targets,
        "marker": POST_REPAIR_EVIDENCE_MARKER,
    }
    argv = [
        sys.executable,
        "-c",
        (
            "import json, sys; "
            "payload=json.loads(sys.argv[1]); "
            "targets=payload.get('targets') or []; "
            "completed=payload.get('completed_targets') or []; "
            "missing=sorted(set(targets)-set(completed)); "
            "unexpected=sorted(set(completed)-set(targets)); "
            "ok=bool(targets) and not missing and not unexpected; "
            "print(payload.get('marker') if ok else 'post-repair-evidence-failed'); "
            "print(json.dumps({"
            "'status':'passed' if ok else 'failed', "
            "'targets':targets, "
            "'completed_targets':completed, "
            "'missing_targets':missing, "
            "'unexpected_targets':unexpected"
            "}, sort_keys=True)); "
            "sys.exit(0 if ok else 1)"
        ),
        json.dumps(payload, sort_keys=True),
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
        "evidence_argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": round(duration, 6),
    }


def build_post_repair_evidence_check_record(
    guarded_repair_execution_result: Mapping[str, Any],
    *,
    allow_post_repair_evidence_check: bool,
    subprocess_result: Mapping[str, Any] | None = None,
    source: str = "post-repair-evidence-check",
) -> dict[str, Any]:
    _validate_guarded_repair_execution_result(guarded_repair_execution_result)

    guarded_result_id = _clean(
        guarded_repair_execution_result.get("guarded_repair_execution_result_id")
    )
    readiness_gate_id = _clean(
        guarded_repair_execution_result.get("real_execution_repair_readiness_gate_id")
    )
    feedback_id = _clean(
        guarded_repair_execution_result.get("real_execution_repair_noop_feedback_id")
    )
    noop_result_id = _clean(
        guarded_repair_execution_result.get("real_execution_repair_noop_result_id")
    )
    envelope_id = _clean(
        guarded_repair_execution_result.get("real_execution_repair_dry_run_envelope_id")
    )
    final_gate_id = _clean(
        guarded_repair_execution_result.get("real_execution_repair_final_gate_id")
    )
    rendered_command_id = _clean(guarded_repair_execution_result.get("rendered_command_id"))

    check_id = _stable_id(
        "replay-retry-post-repair-evidence-check",
        guarded_result_id,
        readiness_gate_id,
        feedback_id,
        noop_result_id,
        envelope_id,
        final_gate_id,
        rendered_command_id,
        str(bool(allow_post_repair_evidence_check)).lower(),
    )

    targets = _repair_targets(guarded_repair_execution_result)
    completed_targets = _completed_repair_targets(guarded_repair_execution_result)
    missing_targets = sorted(set(targets) - set(completed_targets))
    unexpected_targets = sorted(set(completed_targets) - set(targets))

    subprocess_result = (
        subprocess_result if isinstance(subprocess_result, Mapping) else {}
    )
    stdout = str(subprocess_result.get("stdout") or "")
    stderr = str(subprocess_result.get("stderr") or "")
    exit_code = (
        int(subprocess_result.get("exit_code"))
        if "exit_code" in subprocess_result
        else None
    )
    duration_seconds = float(subprocess_result.get("duration_seconds") or 0.0)
    evidence_argv = _safe_list(subprocess_result.get("evidence_argv"))
    marker_observed = POST_REPAIR_EVIDENCE_MARKER in stdout

    if not allow_post_repair_evidence_check:
        post_repair_status = "rejected"
        reason = "post_repair_evidence_check_not_allowed"
        next_action = "authorize_post_repair_evidence_check"
        evidence_check_enabled = False
        evidence_check_execution_performed = False
        evidence_check_subprocess_invoked = False
        execution_performed = False
        subprocess_invoked = False
        repair_outcome_verified = False
    else:
        evidence_check_enabled = True
        evidence_check_execution_performed = True
        evidence_check_subprocess_invoked = True
        execution_performed = True
        subprocess_invoked = True
        repair_outcome_verified = (
            exit_code == 0
            and marker_observed
            and bool(targets)
            and completed_targets == targets
            and not missing_targets
            and not unexpected_targets
        )
        post_repair_status = "passed" if repair_outcome_verified else "failed"
        reason = (
            "post_repair_evidence_check_passed"
            if repair_outcome_verified
            else "post_repair_evidence_check_failed"
        )
        next_action = (
            "close_repair_loop"
            if repair_outcome_verified
            else "investigate_post_repair_failure"
        )

    payload = {
        "post_repair_evidence_check_id": check_id,
        "guarded_repair_execution_result_id": guarded_result_id,
        "real_execution_repair_readiness_gate_id": readiness_gate_id,
        "real_execution_repair_noop_feedback_id": feedback_id,
        "real_execution_repair_noop_result_id": noop_result_id,
        "real_execution_repair_dry_run_envelope_id": envelope_id,
        "real_execution_repair_final_gate_id": final_gate_id,
        "real_execution_repair_approval_transition_id": _clean(
            guarded_repair_execution_result.get(
                "real_execution_repair_approval_transition_id"
            )
        ),
        "real_execution_repair_approval_id": _clean(
            guarded_repair_execution_result.get("real_execution_repair_approval_id")
        ),
        "real_execution_read_only_repair_action_bundle_review_id": _clean(
            guarded_repair_execution_result.get(
                "real_execution_read_only_repair_action_bundle_review_id"
            )
        ),
        "real_execution_read_only_repair_action_bundle_id": _clean(
            guarded_repair_execution_result.get(
                "real_execution_read_only_repair_action_bundle_id"
            )
        ),
        "real_execution_read_only_repair_plan_id": _clean(
            guarded_repair_execution_result.get(
                "real_execution_read_only_repair_plan_id"
            )
        ),
        "real_execution_read_only_feedback_id": _clean(
            guarded_repair_execution_result.get("real_execution_read_only_feedback_id")
        ),
        "real_execution_read_only_execution_result_id": _clean(
            guarded_repair_execution_result.get(
                "real_execution_read_only_execution_result_id"
            )
        ),
        "real_execution_read_only_readiness_gate_id": _clean(
            guarded_repair_execution_result.get(
                "real_execution_read_only_readiness_gate_id"
            )
        ),
        "controlled_execution_result_id": _clean(
            guarded_repair_execution_result.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(guarded_repair_execution_result.get("plan_id")),
        "proposal_id": _clean(guarded_repair_execution_result.get("proposal_id")),
        "approval_id": _clean(guarded_repair_execution_result.get("approval_id")),
        "timeout_profile": _clean(
            guarded_repair_execution_result.get("timeout_profile")
        )
        or "standard",
        "decision_mode": _clean(guarded_repair_execution_result.get("decision_mode"))
        or "manual",
        "post_repair_status": post_repair_status,
        "post_repair_evidence_check_allowed": bool(
            allow_post_repair_evidence_check
        ),
        "post_repair_evidence_check_enabled": evidence_check_enabled,
        "post_repair_evidence_marker": POST_REPAIR_EVIDENCE_MARKER,
        "post_repair_evidence_marker_observed": marker_observed,
        "post_repair_evidence_exit_code": exit_code,
        "post_repair_evidence_stdout": stdout,
        "post_repair_evidence_stderr": stderr,
        "post_repair_evidence_duration_seconds": duration_seconds,
        "post_repair_evidence_argv": evidence_argv,
        "repair_outcome_verified": repair_outcome_verified,
        "repair_targets_expected": targets,
        "repair_targets_completed": completed_targets,
        "repair_targets_missing": missing_targets,
        "repair_targets_unexpected": unexpected_targets,
        "repair_targets_expected_count": len(targets),
        "repair_targets_verified_count": len(completed_targets),
        "source_guarded_repair_execution_status": _clean(
            guarded_repair_execution_result.get("repair_execution_status")
        ),
        "source_guarded_repair_execution_allowed": bool(
            guarded_repair_execution_result.get("repair_execution_allowed")
        ),
        "source_guarded_repair_marker_observed": bool(
            guarded_repair_execution_result.get("guarded_repair_marker_observed")
        ),
        "source_guarded_repair_exit_code": guarded_repair_execution_result.get(
            "exit_code"
        ),
        "source_guarded_repair_next_action": _clean(
            guarded_repair_execution_result.get("recommended_next_action")
        ),
        "source_repair_actions_executed": bool(
            guarded_repair_execution_result.get("repair_actions_executed")
        ),
        "source_repair_bundle_executed": bool(
            guarded_repair_execution_result.get("repair_bundle_executed")
        ),
        "source_repair_command_executed": bool(
            guarded_repair_execution_result.get("repair_command_executed")
        ),
        "source_rendered_command_executed": bool(
            guarded_repair_execution_result.get("rendered_command_executed")
        ),
        "source_dry_run_command_executed": bool(
            guarded_repair_execution_result.get("dry_run_command_executed")
        ),
        "source_repair_execution_enabled": bool(
            guarded_repair_execution_result.get("repair_execution_enabled")
        ),
        "source_real_execution_enabled": bool(
            guarded_repair_execution_result.get("real_execution_enabled")
        ),
        "source_repair_execution_performed": bool(
            guarded_repair_execution_result.get("repair_execution_performed")
        ),
        "source_repair_subprocess_invoked": bool(
            guarded_repair_execution_result.get("repair_subprocess_invoked")
        ),
        "operator_authorized": bool(
            guarded_repair_execution_result.get("operator_authorized")
        ),
        "evidence_check_execution_performed": evidence_check_execution_performed,
        "evidence_check_subprocess_invoked": evidence_check_subprocess_invoked,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": evidence_check_enabled,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "recommended_next_action": next_action,
        "reason": reason,
    }

    return {
        "type": POST_REPAIR_EVIDENCE_CHECK_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    guarded_result_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        guarded_result_id
        and _clean(record.get("guarded_repair_execution_result_id"))
        != guarded_result_id
    ):
        return False
    return True


def _find_existing_check(
    records: list[Mapping[str, Any]],
    *,
    guarded_result_id: str,
    allowed: bool,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != POST_REPAIR_EVIDENCE_CHECK_TYPE:
            continue
        if _clean(item.get("guarded_repair_execution_result_id")) != guarded_result_id:
            continue
        if bool(item.get("post_repair_evidence_check_allowed")) == bool(allowed):
            return item
    return None


async def run_post_repair_evidence_check_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "post-repair-evidence-check"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    guarded_result_id = _clean(
        getattr(args, "guarded_repair_execution_result_id", "")
    )
    allow_post_repair_evidence_check = bool(
        getattr(args, "allow_post_repair_evidence_check", False)
    )
    timeout_seconds = int(getattr(args, "timeout_seconds", 10) or 10)

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    guarded_results = [
        item
        for item in records
        if item.get("type") == GUARDED_REPAIR_EXECUTION_RESULT_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            guarded_result_id=guarded_result_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for guarded_result in guarded_results:
        current_guarded_result_id = _clean(
            guarded_result.get("guarded_repair_execution_result_id")
        )
        if _find_existing_check(
            records,
            guarded_result_id=current_guarded_result_id,
            allowed=allow_post_repair_evidence_check,
        ):
            logger.info(
                "Skipping duplicate post-repair evidence check: result_id=%s allowed=%s",
                current_guarded_result_id,
                allow_post_repair_evidence_check,
            )
            continue

        subprocess_result: Mapping[str, Any] | None = None
        if allow_post_repair_evidence_check:
            subprocess_result = _run_post_repair_verifier(
                targets=_repair_targets(guarded_result),
                completed_targets=_completed_repair_targets(guarded_result),
                timeout_seconds=timeout_seconds,
            )

        record = build_post_repair_evidence_check_record(
            guarded_result,
            allow_post_repair_evidence_check=allow_post_repair_evidence_check,
            subprocess_result=subprocess_result,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)

        logger.info(
            "Published post-repair evidence check: check_id=%s status=%s "
            "verified=%s exit_code=%s repair_execution_enabled=%s subprocess_invoked=%s",
            record.get("post_repair_evidence_check_id"),
            record.get("post_repair_status"),
            record.get("repair_outcome_verified"),
            record.get("post_repair_evidence_exit_code"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info("Post-repair evidence check completed: checks=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run post-repair evidence verification.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--guarded-repair-execution-result-id", default="")
    parser.add_argument("--allow-post-repair-evidence-check", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--source", default="post-repair-evidence-check")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await run_post_repair_evidence_check_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Post-repair evidence check completed: checks={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()