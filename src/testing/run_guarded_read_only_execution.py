"""Run a guarded read-only execution command.

This is the first narrow read-only execution harness. It only executes the
allowlisted replay evidence check module, never uses a shell, and requires an
explicit operator flag.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

READ_ONLY_EXECUTION_RESULT_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_execution_result"
)

READ_ONLY_READINESS_GATE_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_readiness_gate"
)

ALLOWLISTED_MODULE = "src.testing.run_replay_evidence_check"
ALLOWLISTED_ACTIONS = {"REDUCE_RISK"}
ALLOWLISTED_TIMEOUT_PROFILES = {"standard", "patient"}
MAX_CAPTURE_CHARS = 4000


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _tail(value: str, *, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def _parse_read_only_argv(argv: Any) -> tuple[dict[str, str], list[str]]:
    """Validate and parse the single allowlisted read-only command shape."""
    reasons: list[str] = []

    if not isinstance(argv, list) or not argv:
        return {}, ["read_only_argv_not_observed"]

    values = [str(item) for item in argv]

    if len(values) < 3:
        return {}, ["read_only_argv_too_short"]

    if values[1] != "-m":
        reasons.append("read_only_argv_must_use_python_module_mode")
    if values[2] != ALLOWLISTED_MODULE:
        reasons.append("read_only_module_not_allowlisted")

    args = values[3:]
    allowed_keys = {
        "--scenario-id",
        "--action",
        "--directive-id",
        "--timeout-profile",
        "--db-path",
    }

    parsed: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if key not in allowed_keys:
            reasons.append(f"read_only_argv_contains_unexpected_arg:{key}")
            index += 1
            continue
        if index + 1 >= len(args):
            reasons.append(f"read_only_argv_missing_value:{key}")
            break
        value = str(args[index + 1]).strip()
        if not value:
            reasons.append(f"read_only_argv_empty_value:{key}")
        parsed[key] = value
        index += 2

    for required in (
        "--scenario-id",
        "--action",
        "--directive-id",
        "--timeout-profile",
        "--db-path",
    ):
        if required not in parsed:
            reasons.append(f"read_only_argv_missing_required_arg:{required}")

    if parsed.get("--action") not in ALLOWLISTED_ACTIONS:
        reasons.append("read_only_action_not_allowlisted")
    if parsed.get("--timeout-profile") not in ALLOWLISTED_TIMEOUT_PROFILES:
        reasons.append("read_only_timeout_profile_not_allowlisted")

    return parsed, reasons


def _build_safe_argv(parsed: Mapping[str, str]) -> list[str]:
    return [
        sys.executable,
        "-m",
        ALLOWLISTED_MODULE,
        "--scenario-id",
        str(parsed["--scenario-id"]),
        "--action",
        str(parsed["--action"]),
        "--directive-id",
        str(parsed["--directive-id"]),
        "--timeout-profile",
        str(parsed["--timeout-profile"]),
        "--db-path",
        str(parsed["--db-path"]),
    ]


def _validate_gate(gate: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
    reasons: list[str] = []

    if gate.get("type") != READ_ONLY_READINESS_GATE_TYPE:
        reasons.append("invalid_read_only_readiness_gate_type")

    if _clean(gate.get("gate_status")) != "ready_blocked":
        reasons.append("read_only_readiness_gate_not_ready_blocked")
    if not bool(gate.get("read_only_readiness_satisfied")):
        reasons.append("read_only_readiness_not_satisfied")
    if not bool(gate.get("ready_for_guarded_read_only_execution")):
        reasons.append("not_ready_for_guarded_read_only_execution")
    if _clean(gate.get("read_only_approval_latest_status")) != "approved":
        reasons.append("read_only_approval_latest_status_not_approved")
    if _clean(gate.get("read_only_module")) != ALLOWLISTED_MODULE:
        reasons.append("read_only_module_not_allowlisted")

    if bool(gate.get("read_only_execution_enabled")):
        reasons.append("read_only_gate_already_enabled_execution")
    if bool(gate.get("subprocess_invoked")):
        reasons.append("read_only_gate_already_invoked_subprocess")
    if bool(gate.get("execution_performed")):
        reasons.append("read_only_gate_already_performed_execution")
    if bool(gate.get("rendered_command_executed")):
        reasons.append("read_only_gate_already_executed_rendered_command")
    if bool(gate.get("dry_run_envelope_command_executed")):
        reasons.append("read_only_gate_already_executed_dry_run_command")

    parsed, argv_reasons = _parse_read_only_argv(gate.get("read_only_argv"))
    reasons.extend(argv_reasons)

    return parsed, reasons


def _base_result_payload(
    gate: Mapping[str, Any],
    *,
    result_id: str,
    safe_argv: Sequence[str],
    status: str,
    reason: str,
    validation_reasons: list[str],
    operator_authorized: bool,
    allow_guarded_read_only_execution: bool,
) -> dict[str, Any]:
    return {
        "real_execution_read_only_execution_result_id": result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            gate.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            gate.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            gate.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            gate.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            gate.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            gate.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            gate.get("real_execution_dry_run_envelope_id")
        ),
        "real_execution_final_gate_id": _clean(gate.get("real_execution_final_gate_id")),
        "real_execution_approval_transition_id": _clean(
            gate.get("real_execution_approval_transition_id")
        ),
        "real_execution_approval_id": _clean(gate.get("real_execution_approval_id")),
        "real_execution_preflight_id": _clean(gate.get("real_execution_preflight_id")),
        "controlled_execution_result_id": _clean(
            gate.get("controlled_execution_result_id")
        ),
        "rendered_command_id": _clean(gate.get("rendered_command_id")),
        "plan_id": _clean(gate.get("plan_id")),
        "proposal_id": _clean(gate.get("proposal_id")),
        "approval_id": _clean(gate.get("approval_id")),
        "timeout_profile": _clean(gate.get("timeout_profile")) or "standard",
        "decision_mode": _clean(gate.get("decision_mode")) or "manual",
        "read_only_command": _clean(gate.get("read_only_command")),
        "read_only_module": ALLOWLISTED_MODULE,
        "read_only_argv": list(safe_argv),
        "operator_authorized": operator_authorized,
        "allow_guarded_read_only_execution": allow_guarded_read_only_execution,
        "status": status,
        "reason": reason,
        "validation_reasons": validation_reasons,
    }


def build_rejected_read_only_execution_result(
    gate: Mapping[str, Any],
    *,
    reason: str,
    validation_reasons: list[str],
    operator_authorized: bool,
    allow_guarded_read_only_execution: bool,
    source: str,
) -> dict[str, Any]:
    gate_id = _clean(gate.get("real_execution_read_only_readiness_gate_id"))
    rendered_command_id = _clean(gate.get("rendered_command_id"))
    result_id = _stable_id(
        "replay-retry-real-read-only-execution-result",
        gate_id,
        rendered_command_id,
        "rejected",
        reason,
    )

    payload = _base_result_payload(
        gate,
        result_id=result_id,
        safe_argv=[],
        status="rejected",
        reason=reason,
        validation_reasons=validation_reasons,
        operator_authorized=operator_authorized,
        allow_guarded_read_only_execution=allow_guarded_read_only_execution,
    )
    payload.update(
        {
            "read_only_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "subprocess_invoked": False,
            "execution_performed": False,
            "read_only_command_executed": False,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
            "exit_code": None,
            "duration_seconds": 0.0,
            "stdout": "",
            "stderr": "",
        }
    )

    return {
        "type": READ_ONLY_EXECUTION_RESULT_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def run_guarded_read_only_execution_from_gate(
    gate: Mapping[str, Any],
    *,
    operator_authorized: bool,
    allow_guarded_read_only_execution: bool,
    timeout_seconds: float,
    source: str = "guarded-read-only-execution",
) -> dict[str, Any]:
    parsed, validation_reasons = _validate_gate(gate)

    if not operator_authorized:
        validation_reasons.append("operator_not_authorized")
    if not allow_guarded_read_only_execution:
        validation_reasons.append("guarded_read_only_execution_flag_required")

    if validation_reasons:
        return build_rejected_read_only_execution_result(
            gate,
            reason="guarded_read_only_execution_rejected",
            validation_reasons=validation_reasons,
            operator_authorized=operator_authorized,
            allow_guarded_read_only_execution=allow_guarded_read_only_execution,
            source=source,
        )

    safe_argv = _build_safe_argv(parsed)
    gate_id = _clean(gate.get("real_execution_read_only_readiness_gate_id"))
    rendered_command_id = _clean(gate.get("rendered_command_id"))
    result_id = _stable_id(
        "replay-retry-real-read-only-execution-result",
        gate_id,
        rendered_command_id,
        "executed",
        " ".join(safe_argv),
    )

    started = time.monotonic()
    completed = subprocess.run(
        safe_argv,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=os.environ.copy(),
    )
    duration_seconds = round(time.monotonic() - started, 6)

    payload = _base_result_payload(
        gate,
        result_id=result_id,
        safe_argv=safe_argv,
        status="executed" if completed.returncode == 0 else "failed",
        reason=(
            "guarded_read_only_execution_completed"
            if completed.returncode == 0
            else "guarded_read_only_execution_failed"
        ),
        validation_reasons=[],
        operator_authorized=operator_authorized,
        allow_guarded_read_only_execution=allow_guarded_read_only_execution,
    )
    payload.update(
        {
            "read_only_execution_enabled": True,
            "real_execution_enabled": False,
            "subprocess_enabled": True,
            "subprocess_invoked": True,
            "execution_performed": True,
            "read_only_command_executed": True,
            "rendered_command_executed": True,
            "dry_run_envelope_command_executed": True,
            "exit_code": int(completed.returncode),
            "duration_seconds": duration_seconds,
            "stdout": _tail(completed.stdout or ""),
            "stderr": _tail(completed.stderr or ""),
        }
    )

    return {
        "type": READ_ONLY_EXECUTION_RESULT_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    readiness_gate_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        readiness_gate_id
        and _clean(record.get("real_execution_read_only_readiness_gate_id"))
        != readiness_gate_id
    ):
        return False
    return True


def _find_existing_result(
    records: list[Mapping[str, Any]],
    *,
    readiness_gate_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != READ_ONLY_EXECUTION_RESULT_TYPE:
            continue
        if (
            _clean(item.get("real_execution_read_only_readiness_gate_id"))
            == readiness_gate_id
        ):
            return item
    return None


async def run_guarded_read_only_executions(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "guarded-read-only-execution"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    readiness_gate_id = _clean(
        getattr(args, "real_execution_read_only_readiness_gate_id", "")
    )
    operator_authorized = bool(getattr(args, "operator_authorized", False))
    allow_guarded = bool(getattr(args, "allow_guarded_read_only_execution", False))
    timeout_seconds = float(getattr(args, "timeout_seconds", 30.0) or 30.0)

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    gates = [
        item
        for item in records
        if item.get("type") == READ_ONLY_READINESS_GATE_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            readiness_gate_id=readiness_gate_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for gate in gates:
        current_gate_id = _clean(
            gate.get("real_execution_read_only_readiness_gate_id")
        )
        if _find_existing_result(records, readiness_gate_id=current_gate_id):
            logger.info(
                "Skipping duplicate guarded read-only execution: readiness_gate_id=%s",
                current_gate_id,
            )
            continue

        record = run_guarded_read_only_execution_from_gate(
            gate,
            operator_authorized=operator_authorized,
            allow_guarded_read_only_execution=allow_guarded,
            timeout_seconds=timeout_seconds,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published guarded read-only execution result: result_id=%s status=%s exit_code=%s subprocess_invoked=%s execution_performed=%s",
            record.get("real_execution_read_only_execution_result_id"),
            record.get("status"),
            record.get("exit_code"),
            record.get("subprocess_invoked"),
            record.get("execution_performed"),
        )

    logger.info(
        "Guarded read-only execution completed: results=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run guarded read-only execution for a readiness gate.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-readiness-gate-id", default="")
    parser.add_argument("--source", default="guarded-read-only-execution")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--operator-authorized", action="store_true")
    parser.add_argument("--allow-guarded-read-only-execution", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await run_guarded_read_only_executions(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Guarded read-only execution completed: results={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()