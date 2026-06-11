"""Build read-only execution readiness gate records.

This module consumes immutable read-only approval transitions and publishes a
consolidated readiness gate for future guarded read-only execution. It never
enables execution and never invokes subprocesses.
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

REAL_READ_ONLY_READINESS_GATE_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_readiness_gate"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_bool(value: Any) -> bool:
    return bool(value)


def build_real_execution_read_only_readiness_gate_record(
    transition: Mapping[str, Any],
    *,
    source: str = "real-execution-read-only-readiness-gate",
) -> dict[str, Any]:
    transition_id = _clean(
        transition.get("real_execution_read_only_approval_transition_id")
    )
    read_only_approval_id = _clean(
        transition.get("real_execution_read_only_approval_id")
    )
    read_only_final_gate_id = _clean(
        transition.get("real_execution_read_only_final_gate_id")
    )
    read_only_promotion_id = _clean(
        transition.get("real_execution_read_only_promotion_id")
    )
    noop_result_id = _clean(transition.get("real_execution_noop_result_id"))
    dry_run_envelope_id = _clean(
        transition.get("real_execution_dry_run_envelope_id")
    )
    real_final_gate_id = _clean(transition.get("real_execution_final_gate_id"))
    real_approval_transition_id = _clean(
        transition.get("real_execution_approval_transition_id")
    )
    real_approval_id = _clean(transition.get("real_execution_approval_id"))
    preflight_id = _clean(transition.get("real_execution_preflight_id"))
    controlled_result_id = _clean(transition.get("controlled_execution_result_id"))
    rendered_command_id = _clean(transition.get("rendered_command_id"))
    plan_id = _clean(transition.get("plan_id"))
    proposal_id = _clean(transition.get("proposal_id"))
    approval_id = _clean(transition.get("approval_id"))
    timeout_profile = _clean(transition.get("timeout_profile")) or "standard"
    decision_mode = _clean(transition.get("decision_mode")) or "manual"

    read_only_command = _clean(transition.get("read_only_command"))
    read_only_module = _clean(transition.get("read_only_module"))
    read_only_argv = transition.get("read_only_argv")

    from_status = _clean(transition.get("from_status"))
    to_status = _clean(transition.get("to_status"))

    if not transition_id:
        raise ValueError("real_execution_read_only_approval_transition_id is required")
    if not read_only_approval_id:
        raise ValueError("real_execution_read_only_approval_id is required")
    if not read_only_final_gate_id:
        raise ValueError("real_execution_read_only_final_gate_id is required")
    if not read_only_promotion_id:
        raise ValueError("real_execution_read_only_promotion_id is required")
    if not noop_result_id:
        raise ValueError("real_execution_noop_result_id is required")
    if not dry_run_envelope_id:
        raise ValueError("real_execution_dry_run_envelope_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    precondition_failures: list[str] = []

    if from_status != "pending":
        precondition_failures.append("read_only_transition_from_status_not_pending")
    if to_status != "approved":
        precondition_failures.append("read_only_transition_not_approved")
    if read_only_module != "src.testing.run_replay_evidence_check":
        precondition_failures.append("read_only_module_not_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        precondition_failures.append("read_only_argv_not_observed")

    if _safe_bool(transition.get("read_only_execution_enabled")):
        precondition_failures.append("transition_enabled_read_only_execution")
    if _safe_bool(transition.get("real_execution_enabled")):
        precondition_failures.append("transition_enabled_real_execution")
    if _safe_bool(transition.get("subprocess_enabled")):
        precondition_failures.append("transition_enabled_subprocess")
    if _safe_bool(transition.get("subprocess_invoked")):
        precondition_failures.append("transition_invoked_subprocess")
    if _safe_bool(transition.get("execution_performed")):
        precondition_failures.append("transition_performed_execution")
    if _safe_bool(transition.get("rendered_command_executed")):
        precondition_failures.append("transition_executed_rendered_command")
    if _safe_bool(transition.get("dry_run_envelope_command_executed")):
        precondition_failures.append("transition_executed_dry_run_command")

    read_only_readiness_satisfied = not precondition_failures
    gate_status = "ready_blocked" if read_only_readiness_satisfied else "blocked"

    blocking_reasons = [
        "guarded_read_only_execution_requires_separate_pr",
        *precondition_failures,
    ]

    readiness_gate_id = _stable_id(
        "replay-retry-real-read-only-readiness-gate",
        transition_id,
        read_only_approval_id,
        rendered_command_id,
        to_status,
    )

    payload = {
        "real_execution_read_only_readiness_gate_id": readiness_gate_id,
        "real_execution_read_only_approval_transition_id": transition_id,
        "real_execution_read_only_approval_id": read_only_approval_id,
        "real_execution_read_only_final_gate_id": read_only_final_gate_id,
        "real_execution_read_only_promotion_id": read_only_promotion_id,
        "real_execution_noop_result_id": noop_result_id,
        "real_execution_dry_run_envelope_id": dry_run_envelope_id,
        "real_execution_final_gate_id": real_final_gate_id,
        "real_execution_approval_transition_id": real_approval_transition_id,
        "real_execution_approval_id": real_approval_id,
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "read_only_command": read_only_command,
        "read_only_module": read_only_module,
        "read_only_argv": read_only_argv if isinstance(read_only_argv, list) else [],
        "read_only_approval_from_status": from_status,
        "read_only_approval_latest_status": to_status,
        "read_only_readiness_satisfied": read_only_readiness_satisfied,
        "ready_for_guarded_read_only_execution": read_only_readiness_satisfied,
        "gate_status": gate_status,
        "precondition_failures": precondition_failures,
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "guarded_read_only_execution_requires_separate_pr",
        "blocking_reasons": blocking_reasons,
    }

    return {
        "type": REAL_READ_ONLY_READINESS_GATE_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    real_execution_read_only_approval_transition_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        real_execution_read_only_approval_transition_id
        and _clean(record.get("real_execution_read_only_approval_transition_id"))
        != real_execution_read_only_approval_transition_id
    ):
        return False
    return True


def _find_existing_gate(
    records: list[Mapping[str, Any]],
    *,
    transition_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_READ_ONLY_READINESS_GATE_TYPE:
            continue
        if (
            _clean(item.get("real_execution_read_only_approval_transition_id"))
            == transition_id
        ):
            return item
    return None


async def build_real_execution_read_only_readiness_gates(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or (
        "real-execution-read-only-readiness-gate"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    transition_id = _clean(
        getattr(args, "real_execution_read_only_approval_transition_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    transitions = [
        item
        for item in records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_approval_transition"
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            real_execution_read_only_approval_transition_id=transition_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for transition in transitions:
        current_transition_id = _clean(
            transition.get("real_execution_read_only_approval_transition_id")
        )
        if _find_existing_gate(records, transition_id=current_transition_id):
            logger.info(
                "Skipping duplicate read-only readiness gate: transition_id=%s",
                current_transition_id,
            )
            continue

        record = build_real_execution_read_only_readiness_gate_record(
            transition,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only readiness gate: gate_id=%s status=%s satisfied=%s execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_read_only_readiness_gate_id"),
            record.get("gate_status"),
            record.get("read_only_readiness_satisfied"),
            record.get("read_only_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info(
        "Read-only readiness gate builder completed: gates=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build read-only execution readiness gate records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument(
        "--real-execution-read-only-approval-transition-id",
        default="",
    )
    parser.add_argument("--source", default="real-execution-read-only-readiness-gate")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_readiness_gates(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Read-only readiness gate builder completed: gates={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()