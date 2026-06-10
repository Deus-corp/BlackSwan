"""Build dry-run real execution envelopes.

This module prepares argv/cwd/env metadata for future guarded execution, but it
never invokes subprocesses and never enables real execution.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import shlex
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

REAL_DRY_RUN_ENVELOPE_TYPE = (
    "replay_lifecycle_retry_real_execution_dry_run_envelope"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_env_snapshot() -> dict[str, str]:
    """Return a minimal non-secret environment snapshot."""
    allowed_keys = (
        "PATH",
        "PYTHONPATH",
        "PWD",
        "VIRTUAL_ENV",
    )
    return {
        key: str(os.environ.get(key) or "")
        for key in allowed_keys
        if os.environ.get(key)
    }


def build_real_execution_dry_run_envelope_record(
    final_gate: Mapping[str, Any],
    *,
    source: str = "real-execution-dry-run-envelope",
) -> dict[str, Any]:
    """Build a no-subprocess dry-run execution envelope."""
    real_execution_final_gate_id = _clean(
        final_gate.get("real_execution_final_gate_id")
    )
    real_execution_approval_transition_id = _clean(
        final_gate.get("real_execution_approval_transition_id")
    )
    real_execution_approval_id = _clean(final_gate.get("real_execution_approval_id"))
    real_execution_preflight_id = _clean(final_gate.get("real_execution_preflight_id"))
    controlled_execution_result_id = _clean(
        final_gate.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(final_gate.get("rendered_command_id"))
    plan_id = _clean(final_gate.get("plan_id"))
    proposal_id = _clean(final_gate.get("proposal_id"))
    approval_id = _clean(final_gate.get("approval_id"))
    command = _clean(final_gate.get("command"))
    timeout_profile = _clean(final_gate.get("timeout_profile")) or "standard"
    decision_mode = _clean(final_gate.get("decision_mode")) or "manual"

    if not real_execution_final_gate_id:
        raise ValueError("real_execution_final_gate_id is required")
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
    if not command:
        raise ValueError("command is required")

    argv = shlex.split(command)
    cwd = os.getcwd()
    env = _safe_env_snapshot()

    envelope_id = _stable_id(
        "replay-retry-real-dry-run-envelope",
        real_execution_final_gate_id,
        real_execution_approval_transition_id,
        rendered_command_id,
        command,
    )

    payload = {
        "real_execution_dry_run_envelope_id": envelope_id,
        "real_execution_final_gate_id": real_execution_final_gate_id,
        "real_execution_approval_transition_id": real_execution_approval_transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "command": command,
        "argv": argv,
        "cwd": cwd,
        "env": env,
        "env_keys": sorted(env.keys()),
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "dry_run_only": True,
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "real_execution_dry_run_envelope_recorded",
    }

    return {
        "type": REAL_DRY_RUN_ENVELOPE_TYPE,
        "real_execution_dry_run_envelope_id": envelope_id,
        "real_execution_final_gate_id": real_execution_final_gate_id,
        "real_execution_approval_transition_id": real_execution_approval_transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "command": command,
        "argv": argv,
        "cwd": cwd,
        "env_keys": sorted(env.keys()),
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "dry_run_only": True,
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "real_execution_dry_run_envelope_recorded",
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    real_execution_final_gate_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_final_gate_id
        and _clean(record.get("real_execution_final_gate_id"))
        != real_execution_final_gate_id
    ):
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    return True


def _find_existing_envelope(
    records: list[Mapping[str, Any]],
    *,
    real_execution_final_gate_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_DRY_RUN_ENVELOPE_TYPE:
            continue
        if _clean(item.get("real_execution_final_gate_id")) == real_execution_final_gate_id:
            return item
    return None


async def build_real_execution_dry_run_envelopes(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or (
        "real-execution-dry-run-envelope"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    real_execution_final_gate_id = _clean(
        getattr(args, "real_execution_final_gate_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    final_gates = [
        item
        for item in records
        if item.get("type") == "replay_lifecycle_retry_real_execution_final_gate"
        and _matches_filters(
            item,
            real_execution_final_gate_id=real_execution_final_gate_id,
            rendered_command_id=rendered_command_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for final_gate in final_gates:
        current_final_gate_id = _clean(final_gate.get("real_execution_final_gate_id"))

        if _find_existing_envelope(
            records,
            real_execution_final_gate_id=current_final_gate_id,
        ):
            logger.info(
                "Skipping duplicate real execution dry-run envelope: final_gate_id=%s",
                current_final_gate_id,
            )
            continue

        record = build_real_execution_dry_run_envelope_record(
            final_gate,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution dry-run envelope: envelope_id=%s argv_len=%s dry_run_only=%s subprocess_invoked=%s",
            record.get("real_execution_dry_run_envelope_id"),
            len(record.get("argv") or []),
            record.get("dry_run_only"),
            record.get("subprocess_invoked"),
        )

    logger.info(
        "Real execution dry-run envelope builder completed: envelopes=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build no-subprocess dry-run real execution envelopes.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-final-gate-id", default="")
    parser.add_argument("--source", default="real-execution-dry-run-envelope")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_dry_run_envelopes(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution dry-run envelope builder completed: "
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