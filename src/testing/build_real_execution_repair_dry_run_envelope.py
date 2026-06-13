"""Build repair execution dry-run envelope records.

Consumes a ready-blocked repair execution final gate and emits a dry-run
envelope artifact. This envelope records repair dry-run intent only; it never
executes repair actions, never invokes subprocesses, and never enables arbitrary
real execution.
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

REPAIR_FINAL_GATE_TYPE = "replay_lifecycle_retry_real_execution_repair_final_gate"

REPAIR_DRY_RUN_ENVELOPE_TYPE = (
    "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _source_targets(final_gate: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            _clean(item)
            for item in _safe_list(final_gate.get("source_bundle_targets"))
            if _clean(item)
        }
    )


def build_real_execution_repair_dry_run_envelope_record(
    repair_final_gate: Mapping[str, Any],
    *,
    source: str = "real-execution-repair-dry-run-envelope",
) -> dict[str, Any]:
    final_gate_id = _clean(repair_final_gate.get("real_execution_repair_final_gate_id"))
    transition_id = _clean(
        repair_final_gate.get("real_execution_repair_approval_transition_id")
    )
    repair_approval_id = _clean(
        repair_final_gate.get("real_execution_repair_approval_id")
    )
    review_id = _clean(
        repair_final_gate.get(
            "real_execution_read_only_repair_action_bundle_review_id"
        )
    )
    bundle_id = _clean(
        repair_final_gate.get("real_execution_read_only_repair_action_bundle_id")
    )
    repair_plan_id = _clean(
        repair_final_gate.get("real_execution_read_only_repair_plan_id")
    )
    feedback_id = _clean(repair_final_gate.get("real_execution_read_only_feedback_id"))
    read_only_execution_result_id = _clean(
        repair_final_gate.get("real_execution_read_only_execution_result_id")
    )
    rendered_command_id = _clean(repair_final_gate.get("rendered_command_id"))

    gate_status = _clean(repair_final_gate.get("gate_status"))
    preconditions_satisfied = bool(
        repair_final_gate.get("repair_preconditions_satisfied")
    )
    next_action = _clean(repair_final_gate.get("recommended_next_action"))
    transition_approved = bool(
        repair_final_gate.get("repair_execution_transition_approved")
    )
    operator_authorized = bool(repair_final_gate.get("operator_authorized"))

    if not final_gate_id:
        raise ValueError("real_execution_repair_final_gate_id is required")
    if not transition_id:
        raise ValueError("real_execution_repair_approval_transition_id is required")
    if not repair_approval_id:
        raise ValueError("real_execution_repair_approval_id is required")
    if not review_id:
        raise ValueError(
            "real_execution_read_only_repair_action_bundle_review_id is required"
        )
    if not bundle_id:
        raise ValueError("real_execution_read_only_repair_action_bundle_id is required")
    if not repair_plan_id:
        raise ValueError("real_execution_read_only_repair_plan_id is required")
    if not feedback_id:
        raise ValueError("real_execution_read_only_feedback_id is required")
    if not read_only_execution_result_id:
        raise ValueError("real_execution_read_only_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    if gate_status != "ready_blocked":
        raise ValueError("repair dry-run envelope requires ready_blocked final gate")
    if not preconditions_satisfied:
        raise ValueError("repair dry-run envelope requires satisfied preconditions")
    if next_action != "prepare_repair_execution_dry_run_envelope":
        raise ValueError("repair dry-run envelope requires final gate dry-run action")
    if not transition_approved:
        raise ValueError("repair dry-run envelope requires approved transition")
    if not operator_authorized:
        raise ValueError("repair dry-run envelope requires operator_authorized gate")

    envelope_id = _stable_id(
        "replay-retry-real-repair-dry-run-envelope",
        final_gate_id,
        transition_id,
        repair_approval_id,
        review_id,
        bundle_id,
        repair_plan_id,
        rendered_command_id,
    )

    targets = _source_targets(repair_final_gate)

    payload = {
        "real_execution_repair_dry_run_envelope_id": envelope_id,
        "real_execution_repair_final_gate_id": final_gate_id,
        "real_execution_repair_approval_transition_id": transition_id,
        "real_execution_repair_approval_id": repair_approval_id,
        "real_execution_read_only_repair_action_bundle_review_id": review_id,
        "real_execution_read_only_repair_action_bundle_id": bundle_id,
        "real_execution_read_only_repair_plan_id": repair_plan_id,
        "real_execution_read_only_feedback_id": feedback_id,
        "real_execution_read_only_execution_result_id": read_only_execution_result_id,
        "real_execution_read_only_readiness_gate_id": _clean(
            repair_final_gate.get("real_execution_read_only_readiness_gate_id")
        ),
        "real_execution_read_only_approval_transition_id": _clean(
            repair_final_gate.get("real_execution_read_only_approval_transition_id")
        ),
        "real_execution_read_only_approval_id": _clean(
            repair_final_gate.get("real_execution_read_only_approval_id")
        ),
        "real_execution_read_only_final_gate_id": _clean(
            repair_final_gate.get("real_execution_read_only_final_gate_id")
        ),
        "real_execution_read_only_promotion_id": _clean(
            repair_final_gate.get("real_execution_read_only_promotion_id")
        ),
        "real_execution_noop_result_id": _clean(
            repair_final_gate.get("real_execution_noop_result_id")
        ),
        "real_execution_dry_run_envelope_id": _clean(
            repair_final_gate.get("real_execution_dry_run_envelope_id")
        ),
        "controlled_execution_result_id": _clean(
            repair_final_gate.get("controlled_execution_result_id")
        ),
        "rendered_command_id": rendered_command_id,
        "plan_id": _clean(repair_final_gate.get("plan_id")),
        "proposal_id": _clean(repair_final_gate.get("proposal_id")),
        "approval_id": _clean(repair_final_gate.get("approval_id")),
        "timeout_profile": _clean(repair_final_gate.get("timeout_profile"))
        or "standard",
        "decision_mode": _clean(repair_final_gate.get("decision_mode")) or "manual",
        "repair_dry_run_status": "prepared",
        "dry_run_only": True,
        "repair_dry_run_mode": "repair_action_bundle_validation",
        "repair_dry_run_targets": targets,
        "repair_dry_run_target_count": len(targets),
        "repair_dry_run_report": {
            "mode": "repair_action_bundle_validation",
            "target_count": len(targets),
            "targets": targets,
            "applies_changes": False,
            "invokes_subprocess": False,
            "executes_bundle": False,
        },
        "source_gate_status": gate_status,
        "source_final_gate_ready_blocked": gate_status == "ready_blocked",
        "source_final_gate_preconditions_satisfied": preconditions_satisfied,
        "source_transition_approved": transition_approved,
        "source_review_status": _clean(repair_final_gate.get("source_review_status"))
        or "unknown",
        "source_bundle_status": _clean(repair_final_gate.get("source_bundle_status"))
        or "unknown",
        "source_repair_plan_status": _clean(
            repair_final_gate.get("source_repair_plan_status")
        )
        or "unknown",
        "source_feedback_status": _clean(
            repair_final_gate.get("source_feedback_status")
        )
        or "unknown",
        "source_status": _clean(repair_final_gate.get("source_status")) or "unknown",
        "source_exit_code": repair_final_gate.get("source_exit_code"),
        "source_bundle_item_count": repair_final_gate.get("source_bundle_item_count"),
        "source_bundle_targets": targets,
        "operator_authorized": operator_authorized,
        "requires_operator_review": True,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "recommended_next_action": "prepare_repair_execution_noop_harness",
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
        "reason": "repair_execution_dry_run_envelope_recorded",
    }

    return {
        "type": REPAIR_DRY_RUN_ENVELOPE_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    final_gate_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        final_gate_id
        and _clean(record.get("real_execution_repair_final_gate_id")) != final_gate_id
    ):
        return False
    return True


def _find_existing_envelope(
    records: list[Mapping[str, Any]],
    *,
    final_gate_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REPAIR_DRY_RUN_ENVELOPE_TYPE:
            continue
        if _clean(item.get("real_execution_repair_final_gate_id")) == final_gate_id:
            return item
    return None


async def build_real_execution_repair_dry_run_envelope_records(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = (
        _clean(getattr(args, "source", ""))
        or "real-execution-repair-dry-run-envelope"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    final_gate_id = _clean(getattr(args, "real_execution_repair_final_gate_id", ""))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    final_gates = [
        item
        for item in records
        if item.get("type") == REPAIR_FINAL_GATE_TYPE
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            final_gate_id=final_gate_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for final_gate in final_gates:
        current_gate_id = _clean(final_gate.get("real_execution_repair_final_gate_id"))
        if _find_existing_envelope(records, final_gate_id=current_gate_id):
            logger.info(
                "Skipping duplicate repair dry-run envelope: final_gate_id=%s",
                current_gate_id,
            )
            continue

        record = build_real_execution_repair_dry_run_envelope_record(
            final_gate,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published repair execution dry-run envelope: envelope_id=%s "
            "status=%s targets=%s repair_execution_enabled=%s subprocess_invoked=%s",
            record.get("real_execution_repair_dry_run_envelope_id"),
            record.get("repair_dry_run_status"),
            record.get("repair_dry_run_target_count"),
            record.get("repair_execution_enabled"),
            record.get("subprocess_invoked"),
        )

    logger.info(
        "Repair execution dry-run envelope builder completed: envelopes=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build repair execution dry-run envelope records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-repair-final-gate-id", default="")
    parser.add_argument("--source", default="real-execution-repair-dry-run-envelope")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_repair_dry_run_envelope_records(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Repair execution dry-run envelope builder completed: "
            f"envelopes={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()