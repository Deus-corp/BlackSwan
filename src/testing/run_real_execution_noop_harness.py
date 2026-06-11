"""Run a guarded noop subprocess harness for future real execution plumbing.

This module is the first subprocess boundary, but it never executes the rendered
command or the dry-run envelope argv. It only runs a fixed harmless noop command.
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

REAL_NOOP_RESULT_TYPE = "replay_lifecycle_retry_real_execution_noop_result"

NOOP_ARGV = [
    sys.executable,
    "-c",
    "print('controlled-noop-ok')",
]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_noop_result_record(
    dry_run_envelope: Mapping[str, Any],
    *,
    source: str = "real-execution-noop-harness",
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Run fixed noop subprocess and build a guarded result record."""
    real_execution_dry_run_envelope_id = _clean(
        dry_run_envelope.get("real_execution_dry_run_envelope_id")
    )
    real_execution_final_gate_id = _clean(
        dry_run_envelope.get("real_execution_final_gate_id")
    )
    real_execution_approval_transition_id = _clean(
        dry_run_envelope.get("real_execution_approval_transition_id")
    )
    real_execution_approval_id = _clean(
        dry_run_envelope.get("real_execution_approval_id")
    )
    real_execution_preflight_id = _clean(
        dry_run_envelope.get("real_execution_preflight_id")
    )
    controlled_execution_result_id = _clean(
        dry_run_envelope.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(dry_run_envelope.get("rendered_command_id"))
    plan_id = _clean(dry_run_envelope.get("plan_id"))
    proposal_id = _clean(dry_run_envelope.get("proposal_id"))
    approval_id = _clean(dry_run_envelope.get("approval_id"))
    timeout_profile = _clean(dry_run_envelope.get("timeout_profile")) or "standard"
    decision_mode = _clean(dry_run_envelope.get("decision_mode")) or "manual"
    envelope_command = _clean(dry_run_envelope.get("command"))

    if not real_execution_dry_run_envelope_id:
        raise ValueError("real_execution_dry_run_envelope_id is required")
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

    result_id = _stable_id(
        "replay-retry-real-noop-result",
        real_execution_dry_run_envelope_id,
        real_execution_final_gate_id,
        rendered_command_id,
    )

    started_at = time.time()
    completed = subprocess.run(
        NOOP_ARGV,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    duration_seconds = round(time.time() - started_at, 6)

    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    exit_code = int(completed.returncode)

    payload = {
        "real_execution_noop_result_id": result_id,
        "real_execution_dry_run_envelope_id": real_execution_dry_run_envelope_id,
        "real_execution_final_gate_id": real_execution_final_gate_id,
        "real_execution_approval_transition_id": real_execution_approval_transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "envelope_command": envelope_command,
        "noop_argv": NOOP_ARGV,
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": True,
        "execution_performed": True,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration_seconds,
        "reason": "real_execution_noop_harness_completed",
    }

    return {
        "type": REAL_NOOP_RESULT_TYPE,
        "real_execution_noop_result_id": result_id,
        "real_execution_dry_run_envelope_id": real_execution_dry_run_envelope_id,
        "real_execution_final_gate_id": real_execution_final_gate_id,
        "real_execution_approval_transition_id": real_execution_approval_transition_id,
        "real_execution_approval_id": real_execution_approval_id,
        "real_execution_preflight_id": real_execution_preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "noop_argv": NOOP_ARGV,
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": True,
        "execution_performed": True,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration_seconds,
        "reason": "real_execution_noop_harness_completed",
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    real_execution_dry_run_envelope_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_dry_run_envelope_id
        and _clean(record.get("real_execution_dry_run_envelope_id"))
        != real_execution_dry_run_envelope_id
    ):
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    return True


def _find_existing_noop_result(
    records: list[Mapping[str, Any]],
    *,
    real_execution_dry_run_envelope_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_NOOP_RESULT_TYPE:
            continue
        if (
            _clean(item.get("real_execution_dry_run_envelope_id"))
            == real_execution_dry_run_envelope_id
        ):
            return item
    return None


async def run_real_execution_noop_harness(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Run noop harness for matching dry-run envelopes exactly once."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-noop-harness"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    real_execution_dry_run_envelope_id = _clean(
        getattr(args, "real_execution_dry_run_envelope_id", "")
    )
    timeout_seconds = float(getattr(args, "timeout_seconds", 5.0) or 5.0)

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    envelopes = [
        item
        for item in records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_dry_run_envelope"
        and _matches_filters(
            item,
            real_execution_dry_run_envelope_id=real_execution_dry_run_envelope_id,
            rendered_command_id=rendered_command_id,
        )
        and bool(item.get("dry_run_only")) is True
    ]

    results: list[dict[str, Any]] = []
    for envelope in envelopes:
        current_envelope_id = _clean(
            envelope.get("real_execution_dry_run_envelope_id")
        )

        if _find_existing_noop_result(
            records,
            real_execution_dry_run_envelope_id=current_envelope_id,
        ):
            logger.info(
                "Skipping duplicate real execution noop result: envelope_id=%s",
                current_envelope_id,
            )
            continue

        record = build_real_execution_noop_result_record(
            envelope,
            source=source,
            timeout_seconds=timeout_seconds,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution noop result: result_id=%s exit_code=%s subprocess_invoked=%s noop_only=%s",
            record.get("real_execution_noop_result_id"),
            record.get("exit_code"),
            record.get("subprocess_invoked"),
            record.get("noop_only"),
        )

    logger.info(
        "Real execution noop harness completed: results=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run guarded noop subprocess harness for dry-run envelopes.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-dry-run-envelope-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--source", default="real-execution-noop-harness")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await run_real_execution_noop_harness(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Real execution noop harness completed: results={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()