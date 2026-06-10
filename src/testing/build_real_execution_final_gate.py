"""Build final real execution gate records.

The final gate verifies that an explicit approval transition exists, but it
still remains fail-closed in this phase. It never enables real execution and
never invokes subprocesses.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.testing.controlled_retry_execution_adapter import (
    describe_controlled_retry_execution_adapter_contract,
)
from swarm_config import config

logger = logging.getLogger(__name__)

REAL_FINAL_GATE_TYPE = "replay_lifecycle_retry_real_execution_final_gate"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_final_gate_record(
    transition: Mapping[str, Any],
    *,
    source: str = "real-execution-final-gate",
) -> dict[str, Any]:
    """Build a fail-closed final gate record from an approved transition."""
    real_execution_approval_transition_id = _clean(
        transition.get("real_execution_approval_transition_id")
    )
    real_execution_approval_id = _clean(transition.get("real_execution_approval_id"))
    real_execution_preflight_id = _clean(
        transition.get("real_execution_preflight_id")
    )
    controlled_execution_result_id = _clean(
        transition.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(transition.get("rendered_command_id"))
    plan_id = _clean(transition.get("plan_id"))
    proposal_id = _clean(transition.get("proposal_id"))
    approval_id = _clean(transition.get("approval_id"))
    from_status = _clean(transition.get("from_status")).lower()
    to_status = _clean(transition.get("to_status")).lower()
    timeout_profile = _clean(transition.get("timeout_profile")) or "standard"
    decision_mode = _clean(transition.get("decision_mode")) or "manual"
    command = _clean(transition.get("command"))

    if not real_execution_approval_transition_id:
        raise ValueError("real_execution_approval_transition_id is required")
    if not real_execution_approval_id:
        raise ValueError("real_execution_approval_id is required")
    if not real_execution_preflight_id:
        raise ValueError("real_execution_preflight_id is required")
    if not controlled_execution_result_id:
        raise ValueError("controlled_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")
    if from_status != "pending":
        raise ValueError("final gate requires transition from pending")
    if to_status != "approved":
        raise ValueError("final gate requires approved transition")

    adapter_contract = describe_controlled_retry_execution_adapter_contract()
    real_adapter_contract = adapter_contract.get("real_adapter_contract")
    real_adapter_mapping = (
        real_adapter_contract if isinstance(real_adapter_contract, Mapping) else {}
    )

    real_adapter_supported = bool(adapter_contract.get("real_execution_supported"))
    subprocess_supported = bool(adapter_contract.get("subprocess_supported"))
    real_adapter_runnable = bool(real_adapter_mapping.get("runnable"))

    reasons = [
        "real_adapter_not_supported",
        "subprocess_not_supported",
        "explicit_execution_pr_required",
    ]

    final_gate_id = _stable_id(
        "replay-retry-real-final-gate",
        real_execution_approval_transition_id,
        real_execution_approval_id,
        real_execution_preflight_id,
        controlled_execution_result_id,
        rendered_command_id,
    )

    payload = {
        "real_execution_final_gate_id": final_gate_id,
        "real_execution_approval_transition_id": real_execution_approval_transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "from_status": from_status,
        "to_status": to_status,
        "gate_status": "blocked",
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_adapter_supported": real_adapter_supported,
        "real_adapter_runnable": real_adapter_runnable,
        "subprocess_supported": subprocess_supported,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reasons": reasons,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "adapter_contract": adapter_contract,
    }

    return {
        "type": REAL_FINAL_GATE_TYPE,
        "real_execution_final_gate_id": final_gate_id,
        "real_execution_approval_transition_id": real_execution_approval_transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "from_status": from_status,
        "to_status": to_status,
        "gate_status": "blocked",
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_adapter_supported": real_adapter_supported,
        "real_adapter_runnable": real_adapter_runnable,
        "subprocess_supported": subprocess_supported,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reasons": reasons,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    real_execution_approval_transition_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_approval_transition_id
        and _clean(record.get("real_execution_approval_transition_id"))
        != real_execution_approval_transition_id
    ):
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    return True


def _find_existing_final_gate(
    records: list[Mapping[str, Any]],
    *,
    real_execution_approval_transition_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_FINAL_GATE_TYPE:
            continue
        if (
            _clean(item.get("real_execution_approval_transition_id"))
            == real_execution_approval_transition_id
        ):
            return item
    return None


async def build_real_execution_final_gates(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish final real execution gate records from approved transitions."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-final-gate"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    real_execution_approval_transition_id = _clean(
        getattr(args, "real_execution_approval_transition_id", "")
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
        == "replay_lifecycle_retry_real_execution_approval_transition"
        and _matches_filters(
            item,
            real_execution_approval_transition_id=(
                real_execution_approval_transition_id
            ),
            rendered_command_id=rendered_command_id,
        )
        and _clean(item.get("to_status")).lower() == "approved"
    ]

    results: list[dict[str, Any]] = []
    for transition in transitions:
        current_transition_id = _clean(
            transition.get("real_execution_approval_transition_id")
        )

        if _find_existing_final_gate(
            records,
            real_execution_approval_transition_id=current_transition_id,
        ):
            logger.info(
                "Skipping duplicate real execution final gate: transition_id=%s",
                current_transition_id,
            )
            continue

        record = build_real_execution_final_gate_record(
            transition,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution final gate: final_gate_id=%s gate_status=%s ready_for_real_execution=%s would_execute=%s",
            record.get("real_execution_final_gate_id"),
            record.get("gate_status"),
            record.get("ready_for_real_execution"),
            record.get("would_execute"),
        )

    logger.info(
        "Real execution final gate builder completed: final_gates=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed final real execution gate records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Rendered command id filter.",
    )
    parser.add_argument(
        "--real-execution-approval-transition-id",
        default="",
        help="Approval transition id filter.",
    )
    parser.add_argument(
        "--source",
        default="real-execution-final-gate",
        help="CRDT source/node id.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON records.")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_final_gates(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Real execution final gate builder completed: final_gates={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()