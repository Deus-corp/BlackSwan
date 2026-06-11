"""Build explicit read-only execution approval records.

This records operator/audit intent for future read-only execution, but never
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

REAL_READ_ONLY_APPROVAL_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_approval"
)

APPROVAL_STATUSES = {"pending", "approved", "rejected"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_read_only_approval_record(
    final_gate: Mapping[str, Any],
    *,
    approval_status: str = "pending",
    source: str = "real-execution-read-only-approval",
) -> dict[str, Any]:
    status = _clean(approval_status) or "pending"
    if status not in APPROVAL_STATUSES:
        raise ValueError(f"unsupported approval_status: {status}")

    final_gate_id = _clean(final_gate.get("real_execution_read_only_final_gate_id"))
    promotion_id = _clean(final_gate.get("real_execution_read_only_promotion_id"))
    noop_result_id = _clean(final_gate.get("real_execution_noop_result_id"))
    dry_run_envelope_id = _clean(final_gate.get("real_execution_dry_run_envelope_id"))
    real_final_gate_id = _clean(final_gate.get("real_execution_final_gate_id"))
    approval_transition_id = _clean(
        final_gate.get("real_execution_approval_transition_id")
    )
    real_approval_id = _clean(final_gate.get("real_execution_approval_id"))
    preflight_id = _clean(final_gate.get("real_execution_preflight_id"))
    controlled_result_id = _clean(final_gate.get("controlled_execution_result_id"))
    rendered_command_id = _clean(final_gate.get("rendered_command_id"))
    plan_id = _clean(final_gate.get("plan_id"))
    proposal_id = _clean(final_gate.get("proposal_id"))
    approval_id = _clean(final_gate.get("approval_id"))
    timeout_profile = _clean(final_gate.get("timeout_profile")) or "standard"
    decision_mode = _clean(final_gate.get("decision_mode")) or "manual"

    read_only_command = _clean(final_gate.get("read_only_command"))
    read_only_module = _clean(final_gate.get("read_only_module"))
    read_only_argv = final_gate.get("read_only_argv")

    if not final_gate_id:
        raise ValueError("real_execution_read_only_final_gate_id is required")
    if not promotion_id:
        raise ValueError("real_execution_read_only_promotion_id is required")
    if not noop_result_id:
        raise ValueError("real_execution_noop_result_id is required")
    if not dry_run_envelope_id:
        raise ValueError("real_execution_dry_run_envelope_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    approval_record_id = _stable_id(
        "replay-retry-real-read-only-approval",
        final_gate_id,
        promotion_id,
        rendered_command_id,
        status,
    )

    payload = {
        "real_execution_read_only_approval_id": approval_record_id,
        "real_execution_read_only_final_gate_id": final_gate_id,
        "real_execution_read_only_promotion_id": promotion_id,
        "real_execution_noop_result_id": noop_result_id,
        "real_execution_dry_run_envelope_id": dry_run_envelope_id,
        "real_execution_final_gate_id": real_final_gate_id,
        "real_execution_approval_transition_id": approval_transition_id,
        "real_execution_approval_id": real_approval_id,
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "approval_status": status,
        "read_only_command": read_only_command,
        "read_only_module": read_only_module,
        "read_only_argv": read_only_argv if isinstance(read_only_argv, list) else [],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_explicit_approval_required",
    }

    return {
        "type": REAL_READ_ONLY_APPROVAL_TYPE,
        **payload,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    real_execution_read_only_final_gate_id: str,
) -> bool:
    if (
        rendered_command_id
        and _clean(record.get("rendered_command_id")) != rendered_command_id
    ):
        return False
    if (
        real_execution_read_only_final_gate_id
        and _clean(record.get("real_execution_read_only_final_gate_id"))
        != real_execution_read_only_final_gate_id
    ):
        return False
    return True


def _find_existing_approval(
    records: list[Mapping[str, Any]],
    *,
    final_gate_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_READ_ONLY_APPROVAL_TYPE:
            continue
        if _clean(item.get("real_execution_read_only_final_gate_id")) == final_gate_id:
            return item
    return None


async def build_real_execution_read_only_approvals(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-read-only-approval"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    final_gate_id = _clean(getattr(args, "real_execution_read_only_final_gate_id", ""))
    approval_status = _clean(getattr(args, "approval_status", "")) or "pending"

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    final_gates = [
        item
        for item in records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_final_gate"
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            real_execution_read_only_final_gate_id=final_gate_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for gate in final_gates:
        current_gate_id = _clean(gate.get("real_execution_read_only_final_gate_id"))
        if _find_existing_approval(records, final_gate_id=current_gate_id):
            logger.info(
                "Skipping duplicate read-only execution approval: final_gate_id=%s",
                current_gate_id,
            )
            continue

        record = build_real_execution_read_only_approval_record(
            gate,
            approval_status=approval_status,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published read-only execution approval: approval_id=%s status=%s execution_enabled=%s subprocess_enabled=%s",
            record.get("real_execution_read_only_approval_id"),
            record.get("approval_status"),
            record.get("read_only_execution_enabled"),
            record.get("subprocess_enabled"),
        )

    logger.info(
        "Read-only execution approval builder completed: approvals=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build explicit read-only execution approval records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-read-only-final-gate-id", default="")
    parser.add_argument(
        "--approval-status",
        default="pending",
        choices=sorted(APPROVAL_STATUSES),
    )
    parser.add_argument("--source", default="real-execution-read-only-approval")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_approvals(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Read-only execution approval builder completed: approvals={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()