"""Build fail-closed read-only execution final gate records.

This module consumes read-only promotion records and publishes a final gate
artifact for future read-only execution consumes read-only promotion records and publishes a final gate
artifact for future read-only execution. It never invokes subprocesses and never
executes the read-only command.
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

REAL_READ_ONLY_FINAL_GATE_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_final_gate"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_real_execution_read_only_final_gate_record(
    promotion: Mapping[str, Any],
    *,
    source: str = "real-execution-read-only-final-gate",
) -> dict[str, Any]:
    """Build a fail-closed final gate from a read-only promotion record."""
    promotion_id = _clean(promotion.get("real_execution_read_only_promotion_id"))
    noop_result_id = _clean(promotion.get("real_execution_noop_result_id"))
    dry_run_envelope_id = _clean(
        promotion.get("real_execution_dry_run_envelope_id")
    )
    real_final_gate_id = _clean(promotion.get("real_execution_final_gate_id"))
    approval_transition_id = _clean(
        promotion.get("real_execution_approval_transition_id")
    )
    approval_id = _clean(promotion.get("real_execution_approval_id"))
    preflight_id = _clean(promotion.get("real_execution_preflight_id"))
    controlled_result_id = _clean(promotion.get("controlled_execution_result_id"))
    rendered_command_id = _clean(promotion.get("rendered_command_id"))
    plan_id = _clean(promotion.get("plan_id"))
    proposal_id = _clean(promotion.get("proposal_id"))
    replay_approval_id = _clean(promotion.get("approval_id"))
    timeout_profile = _clean(promotion.get("timeout_profile")) or "standard"
    decision_mode = _clean(promotion.get("decision_mode")) or "manual"

    read_only_command = _clean(promotion.get("read_only_command"))
    read_only_module = _clean(promotion.get("read_only_module"))
    read_only_argv = promotion.get("read_only_argv")

    if not promotion_id:
        raise ValueError("real_execution_read_only_promotion_id is required")
    if not noop_result_id:
        raise ValueError("real_execution_noop_result_id is required")
    if not dry_run_envelope_id:
        raise ValueError("real_execution_dry_run_envelope_id is required")
    if not real_final_gate_id:
        raise ValueError("real_execution_final_gate_id is required")
    if not approval_transition_id:
        raise ValueError("real_execution_approval_transition_id is required")
    if not approval_id:
        raise ValueError("real_execution_approval_id is required")
    if not preflight_id:
        raise ValueError("real_execution_preflight_id is required")
    if not controlled_result_id:
        raise ValueError("controlled_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    promotion_status = _clean(promotion.get("promotion_status"))
    read_only_candidate = _safe_bool(promotion.get("read_only_candidate"))
    command_parse_valid = _safe_bool(promotion.get("command_parse_valid"))
    stdout_marker_observed = _safe_bool(promotion.get("stdout_marker_observed"))
    noop_exit_code = _safe_int(promotion.get("noop_exit_code"), default=-1)
    noop_only = _safe_bool(promotion.get("noop_only"))

    rendered_command_executed = _safe_bool(
        promotion.get("rendered_command_executed")
    )
    dry_run_command_executed = _safe_bool(
        promotion.get("dry_run_envelope_command_executed")
    )
    real_execution_enabled = _safe_bool(promotion.get("real_execution_enabled"))
    promotion_subprocess_invoked = _safe_bool(promotion.get("subprocess_invoked"))
    promotion_execution_performed = _safe_bool(promotion.get("execution_performed"))

    precondition_failures: list[str] = []
    if promotion_status != "promoted":
        precondition_failures.append("read_only_promotion_not_promoted")
    if not read_only_candidate:
        precondition_failures.append("read_only_candidate_not_observed")
    if not command_parse_valid:
        precondition_failures.append("read_only_command_parse_not_valid")
    if not stdout_marker_observed:
        precondition_failures.append("noop_stdout_marker_not_observed")
    if noop_exit_code != 0:
        precondition_failures.append("noop_exit_code_not_zero")
    if not noop_only:
        precondition_failures.append("noop_only_source_not_observed")
    if rendered_command_executed:
        precondition_failures.append("promotion_executed_rendered_command")
    if dry_run_command_executed:
        precondition_failures.append("promotion_executed_dry_run_command")
    if real_execution_enabled:
        precondition_failures.append("promotion_enabled_real_execution")
    if promotion_subprocess_invoked:
        precondition_failures.append("promotion_invoked_subprocess")
    if promotion_execution_performed:
        precondition_failures.append("promotion_performed_execution")
    if read_only_module != "src.testing.run_replay_evidence_check":
        precondition_failures.append("read_only_module_not_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        precondition_failures.append("read_only_argv_not_observed")

    promotion_preconditions_satisfied = not precondition_failures

    blocking_reasons = [
        "read_only_execution_requires_separate_pr",
        *precondition_failures,
    ]

    gate_id = _stable_id(
        "replay-retry-real-read-only-final-gate",
        promotion_id,
        noop_result_id,
        dry_run_envelope_id,
        rendered_command_id,
    )

    payload = {
        "real_execution_read_only_final_gate_id": gate_id,
        "real_execution_read_only_promotion_id": promotion_id,
        "real_execution_noop_result_id": noop_result_id,
        "real_execution_dry_run_envelope_id": dry_run_envelope_id,
        "real_execution_final_gate_id": real_final_gate_id,
        "real_execution_approval_transition_id": approval_transition_id,
        "real_execution_approval_id": approval_id,
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": replay_approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "read_only_command": read_only_command,
        "read_only_module": read_only_module,
        "read_only_argv": read_only_argv if isinstance(read_only_argv, list) else [],
        "promotion_status": promotion_status,
        "promotion_preconditions_satisfied": promotion_preconditions_satisfied,
        "precondition_failures": precondition_failures,
        "gate_status": "blocked",
        "ready_for_read_only_execution": False,
        "would_execute": False,
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_requires_separate_pr",
        "blocking_reasons": blocking_reasons,
    }

    return {
        "type": REAL_READ_ONLY_FINAL_GATE_TYPE,
        "real_execution_read_only_final_gate_id": gate_id,
        "real_execution_read_only_promotion_id": promotion_id,
        "real_execution_noop_result_id": noop_result_id,
        "real_execution_dry_run_envelope_id": dry_run_envelope_id,
        "real_execution_final_gate_id": real_final_gate_id,
        "real_execution_approval_transition_id": approval_transition_id,
        "real_execution_approval_id": approval_id,
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": replay_approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "read_only_command": read_only_command,
        "read_only_module": read_only_module,
        "read_only_argv": read_only_argv if isinstance(read_only_argv, list) else [],
        "promotion_status": promotion_status,
        "promotion_preconditions_satisfied": promotion_preconditions_satisfied,
        "precondition_failures": precondition_failures,
        "gate_status": "blocked",
        "ready_for_read_only_execution": False,
        "would_execute": False,
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_requires_separate_pr",
        "blocking_reasons": blocking_reasons,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    real_execution_read_only_promotion_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_read_only_promotion_id
        and _clean(record.get("real_execution_read_only_promotion_id"))
        != real_execution_read_only_promotion_id
    ):
        return False
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    return True


def _find_existing_gate(
    records: list[Mapping[str, Any]],
    *,
    real_execution_read_only_promotion_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_READ_ONLY_FINAL_GATE_TYPE:
            continue
        if (
            _clean(item.get("real_execution_read_only_promotion_id"))
            == real_execution_read_only_promotion_id
        ):
            return item
    return None


async def build_real_execution_read_only_final_gates(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish read-only final gate records from promotions exactly once."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or (
        "real-execution-read-only-final-gate"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    promotion_id = _clean(
        getattr(args, "real_execution_read_only_promotion_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    promotions = [
        item
        for item in records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_promotion"
        and _matches_filters(
            item,
            real_execution_read_only_promotion_id=promotion_id,
            rendered_command_id=rendered_command_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for promotion in promotions:
        current_promotion_id = _clean(
            promotion.get("real_execution_read_only_promotion_id")
        )

        if _find_existing_gate(
            records,
            real_execution_read_only_promotion_id=current_promotion_id,
        ):
            logger.info(
                "Skipping duplicate real execution read-only final gate: promotion_id=%s",
                current_promotion_id,
            )
            continue

        record = build_real_execution_read_only_final_gate_record(
            promotion,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution read-only final gate: gate_id=%s status=%s ready=%s subprocess_invoked=%s execution_performed=%s",
            record.get("real_execution_read_only_final_gate_id"),
            record.get("gate_status"),
            record.get("ready_for_read_only_execution"),
            record.get("subprocess_invoked"),
            record.get("execution_performed"),
        )

    logger.info(
        "Real execution read-only final gate builder completed: final_gates=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed read-only execution final gate records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-promotion-id", default="")
    parser.add_argument("--source", default="real-execution-read-only-final-gate")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_final_gates(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution read-only final gate builder completed: "
            f"final_gates={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()