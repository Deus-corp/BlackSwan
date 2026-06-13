"""Run a guarded repair execution noop harness.

Consumes a prepared repair execution dry-run envelope and executes only a
controlled noop subprocess. This harness never executes repair actions, never
executes the repair bundle, and never enables arbitrary real execution.
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

REPAIR_DRY_RUN_ENVELOPE_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
)

REPAIR_NOOP_RESULT_TYPE = "replay_lifecycle_retry_real_execution_repair_noop_result"

NOOP_MARKER = "controlled-repair-noop-ok"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _repair_targets(envelope: Mapping[str, Any]) -> list[str]:
    targets = envelope.get("repair_dry_run_targets")
    if not isinstance(targets, list):
        targets = envelope.get("source_bundle_targets")
    return sorted({_clean(item) for item in _safe_list(targets) if _clean(item)})


def _validate_envelope_preconditions(envelope: Mapping[str, Any]) -> None:
    envelope_id = _clean(envelope.get("real_execution_repair_dry_run_envelope_id"))
    final_gate_id = _clean(envelope.get("real_execution_repair_final_gate_id"))
    rendered_command_id = _clean(envelope.get("rendered_command_id"))

    if not envelope_id:
        raise ValueError("real_execution_repair_dry_run_envelope_id is required")
    if not final_gate_id:
        raise ValueError("real_execution_repair_final_gate_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    if _clean(envelope.get("repair_dry_run_status")) != "prepared":
        raise ValueError("repair noop harness requires prepared dry-run envelope")
    if not bool(envelope.get("dry_run_only")):
        raise ValueError("repair noop harness requires dry_run_only envelope")
    if _clean(envelope.get("repair_dry_run_mode")) != "repair_action_bundle_validation":
        raise ValueError("repair noop harness requires repair action bundle validation mode")
    if _clean(envelope.get("recommended_next_action")) != "prepare_repair_execution_noop_harness":
        raise ValueError("repair noop harness requires noop next action")
    if not bool(envelope.get("operator_authorized")):
        raise ValueError("repair noop harness requires operator_authorized envelope")
    if not bool(envelope.get("source_final_gate_ready_blocked")):
        raise ValueError("repair noop harness requires ready-blocked final gate source")
    if not bool(envelope.get("source_final_gate_preconditions_satisfied")):
        raise ValueError("repair noop harness requires satisfied final gate preconditions")
    if not bool(envelope.get("source_transition_approved")):
        raise ValueError("repair noop harness requires approved repair transition source")

    if bool(envelope.get("bundle_execution_enabled")):
        raise ValueError("repair noop harness rejects bundle_execution_enabled envelope")
    if bool(envelope.get("repair_execution_enabled")):
        raise ValueError("repair noop harness rejects repair_execution_enabled envelope")
    if bool(envelope.get("real_execution_enabled")):
        raise ValueError("repair noop harness rejects real_execution_enabled envelope")
    if bool(envelope.get("subprocess_enabled")):
        raise ValueError("repair noop harness rejects subprocess_enabled envelope")
    if bool(envelope.get("bundle_execution_performed")):
        raise ValueError("repair noop harness rejects bundle_execution_performed envelope")
    if bool(envelope.get("repair_execution_performed")):
        raise ValueError("repair noop harness rejects repair_execution_performed envelope")
    if bool(envelope.get("execution_performed")):
        raise ValueError("repair noop harness rejects execution_performed envelope")
    if bool(envelope.get("subprocess_invoked")):
        raise ValueError("repair noop harness rejects subprocess_invoked envelope")

    if len(_repair_targets(envelope)) <= 0:
        raise ValueError("repair noop harness requires repair dry-run targets")


def _run_noop_subprocess(*, timeout_seconds: int = 10) -> dict[str, Any]:
    argv = [sys.executable, "-c", f"print({NOOP_MARKER!r})"]
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
        "noop_argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": round(duration, 6),
    }


def build_real_execution_repair_noop_result_record(
    repair_dry_run_envelope: Mapping[str, Any],
    *,
    noop_result: Mapping[str, Any],
    source: str = "real-execution-repair-noop-harness",
) -> dict[str, Any]:
    _validate_envelope_preconditions(repair_dry_run_envelope)

    envelope_id = _clean(
        repair_dry_run_envelope.get("real_execution_repair_dry_run_envelope_id")
    )
    final_gate_id = _clean(
        repair_dry_run_envelope.get("real_execution_repair_final_gate_id")
    )
    transition_id = _clean(
        repair_dry_run_envelope.get("real_execution_repair_approval_transition_id")
    )
    repair_approval_id = _clean(
        repair_dry_run_envelope.get("real_execution_repair_approval_id")
    )
    bundle_id = _clean(
        repair_dry_run_envelope.get("real_execution_read_only_repair_action_bundle_id")
    )
    repair_plan_id = _clean(
        repair_dry_run_envelope.get("real_execution_read_only_repair_plan_id")
    )
    rendered_command_id = _clean(repair_dry_run_envelope.get("rendered_command_id"))

    result_id = _stable_id(
        "replay-retry-real-repair-noop-result",
        envelope_id,
        final_gate_id,
        transition_id,
        repair_approval_id,
        bundle_id,
        repair_plan_id,
        rendered_command_id,
    )

    stdout = str(noop_result.get("stdout") or "")
    stderr = str(noop_result.get("stderr") or "")
    exit_code = int(noop_result.get("exit_code") or 0)
    duration_seconds = float(noop_result.get("duration_seconds") or 0.0)
    noop_argv = _safe_list(noop_result.get("noop_argv"))

    stdout_marker_observed = NOOP_MARKER in stdout
    noop_status = "completed" if exit_code == 0 and stdout_marker_observed else "failed"
    targets = _repair_targets(repair_dry_run_envelope)

    payload = {
        "real_execution_repair_noop_result_id": result_id,
        "real_execution_repair_dry_run_envelope_id": envelope_id,
        "real_execution_repair_final_gate_id": final_gate_id,
        "real_execution_repair_approval_transition_id": transition_id,
        "real_execution_repair_approval_id": repair_approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": _clean(
            repair_dry_run_envelope.get(
                "real_execution_read_only_repair_action_bundle_review_id"
            )
        ),
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": _clean(
            repair_dry_run_envelope.get("real_execution_read_only_feedback_id")
        ),
        "real_execution_read_only_execution_result_id": _clean(
            repair_dry_run_envelope.get("real_execution_read_only_execution_result_id")
        ),
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_dry_run_envelope.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_dry_run_envelope.get(
                "real_execution_read_only_approval_transition_id"
            )
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_dry_run_envelope.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_dry_run_envelope.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_dry_run_envelope.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_dry_run_envelope.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_dry_run_envelope.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_dry_run_envelope.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_dry_run_envelope.get("plan_id")),
        "proposal_id": _clean(repair_dry_run_envelope.get("proposal_id")),
        "approval_id": _clean(repair_dry_run_envelope.get("approval_id")),
        "timeout_profile": _clean(repair_dry_run_envelope.get("timeout_profile"))
        or "standard",
        "decision_mode": _clean(repair_dry_run_envelope.get("decision_mode"))
        or "manual",
        "repair_noop_status": noop_status,
        "noop_only": True,
        "noop_marker": NOOP_MARKER,
        "noop_stdout_marker_observed": stdout_marker_observed,
        "noop_argv": noop_argv,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration_seconds,
        "source_envelope_status": _clean(
            repair_dry_run_envelope.get("repair_dry_run_status")
        )
        or "unknown",
        "source_dry_run_only": bool(repair_dry_run_envelope.get("dry_run_only")),
        "source_repair_dry_run_mode": _clean(
            repair_dry_run_envelope.get("repair_dry_run_mode")
        )
        or "unknown",
        "source_repair_dry_run_target_count": len(targets),
        "source_repair_dry_run_targets": targets,
        "source_final_gate_id": final_gate_id,
        "source_final_gate_ready_blocked": bool(
            repair_dry_run_envelope.get("source_final_gate_ready_blocked")
        ),
        "source_transition_approved": bool(
            repair_dry_run_envelope.get("source_transition_approved")
        ),
        "operator_authorized": bool(
            repair_dry_run_envelope.get("operator_authorized")
        ),
        "dry_run_envelope_executed": False,
        "repair_dry_run_envelope_executed": False,
        "repair_actions_executed": False,
        "repair_bundle_executed": False,
        "repair_command_executed": False,
        "rendered_command_executed": False,
        "dry_run_command_executed": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": True,
        "subprocess_invoked": True,
        "recommended_next_action": (
            "inspect_repair_noop_result"
            if noop_status == "completed"
            else "investigate_repair_noop_harness_failure"
        ),
        "reason": (
            "repair_execution_noop_harness_completed"
            if noop_status == "completed"
            else "repair_execution_noop_harness_failed"
        ),
    }

    return {
        "type": REPAIR_NOOP_RESULT_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    envelope_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        envelope_id
        and _clean(record.get("real_execution_repair_dry_run_envelope_id"))
        != envelope_id
    ):
        return False
    return True


def _find_existing_noop_result(
    records: list[Mapping[str, Any]],
    *,
    envelope_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_NOOP_RESULT_TYPE:
            continue
        if (
            _clean(item.get("real_execution_repair_dry_run_envelope_id"))
            == envelope_id
        ):
            return item
    return None


async def run_real_execution_repair_noop_harness_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-repair-noop-harness"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    envelope_id = _clean(
        getattr(args, "real_execution_repair_dry_run_envelope_id", "")
    )
    timeout_seconds = int(getattr(args, "timeout_seconds", 10) or 10)

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    envelopes = [
        item
        for item in records
        if item.get("type") == REPAIR_DRY_RUN_ENVELOPE_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            envelope_id=envelope_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for envelope in envelopes:
        current_envelope_id = _clean(
            envelope.get("real_execution_repair_dry_run_envelope_id")
        )
        if _find_existing_noop_result(records, envelope_id=current_envelope_id):
            logger.info(
                "Skipping duplicate repair noop result: envelope_id=%s",
                current_envelope_id,
            )
            continue

        noop_result = _run_noop_subprocess(timeout_seconds=timeout_seconds)
        record = build_real_execution_repair_noop_result_record(
            envelope,
            noop_result=noop_result,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published repair execution noop result: result_id=%s status=%s "
            "exit_code=%s subprocess_invoked=%s repair_actions_executed=%s",
            record.get("real_execution_repair_noop_result_id"),
            record.get("repair_noop_status"),
            record.get("exit_code"),
            record.get("subprocess_invoked"),
            record.get("repair_actions_executed"),
        )

    logger.info("Repair execution noop harness completed: results=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run guarded repair execution noop harness.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-repair-dry-run-envelope-id", default="")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--source", default="real-execution-repair-noop-harness")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await run_real_execution_repair_noop_harness_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Repair execution noop harness completed: results={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()