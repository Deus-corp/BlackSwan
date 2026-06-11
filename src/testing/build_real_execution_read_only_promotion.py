"""Build guarded read-only evidence command promotion records.

This module promotes a dry-run envelope command to a read-only candidate after a
successful noop harness result. It does not execute the rendered command and does
not invoke any subprocess.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import shlex
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

REAL_READ_ONLY_PROMOTION_TYPE = (
    "replay_lifecycle_retry_real_execution_read_only_promotion"
)

ALLOWED_READ_ONLY_MODULE = "src.testing.run_replay_evidence_check"
REQUIRED_FLAGS = ("--scenario-id", "--directive-id", "--timeout-profile")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _payload_mapping(record: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _envelope_command(noop_result: Mapping[str, Any]) -> str:
    payload = _payload_mapping(noop_result)
    return _clean(
        noop_result.get("envelope_command")
        or payload.get("envelope_command")
        or noop_result.get("command")
        or payload.get("command")
    )


def _parse_command(command: str) -> dict[str, Any]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return {
            "valid": False,
            "argv": [],
            "module": "",
            "reasons": [f"command_parse_error:{exc}"],
        }

    module = ""
    if "-m" in argv:
        index = argv.index("-m")
        if index + 1 < len(argv):
            module = argv[index + 1]

    reasons: list[str] = []
    if not argv:
        reasons.append("empty_command")
    if module != ALLOWED_READ_ONLY_MODULE:
        reasons.append("read_only_module_not_allowlisted")
    for flag in REQUIRED_FLAGS:
        if flag not in argv:
            reasons.append(f"missing_required_flag:{flag}")

    return {
        "valid": not reasons,
        "argv": argv,
        "module": module,
        "reasons": reasons,
    }


def build_real_execution_read_only_promotion_record(
    noop_result: Mapping[str, Any],
    *,
    source: str = "real-execution-read-only-promotion",
) -> dict[str, Any]:
    """Build a no-execution read-only promotion record from a noop result."""
    real_execution_noop_result_id = _clean(
        noop_result.get("real_execution_noop_result_id")
    )
    real_execution_dry_run_envelope_id = _clean(
        noop_result.get("real_execution_dry_run_envelope_id")
    )
    real_execution_final_gate_id = _clean(
        noop_result.get("real_execution_final_gate_id")
    )
    real_execution_approval_transition_id = _clean(
        noop_result.get("real_execution_approval_transition_id")
    )
    real_execution_approval_id = _clean(noop_result.get("real_execution_approval_id"))
    real_execution_preflight_id = _clean(noop_result.get("real_execution_preflight_id"))
    controlled_execution_result_id = _clean(
        noop_result.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(noop_result.get("rendered_command_id"))
    plan_id = _clean(noop_result.get("plan_id"))
    proposal_id = _clean(noop_result.get("proposal_id"))
    approval_id = _clean(noop_result.get("approval_id"))
    timeout_profile = _clean(noop_result.get("timeout_profile")) or "standard"
    decision_mode = _clean(noop_result.get("decision_mode")) or "manual"

    if not real_execution_noop_result_id:
        raise ValueError("real_execution_noop_result_id is required")
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

    noop_only = bool(noop_result.get("noop_only"))
    rendered_command_executed = bool(noop_result.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        noop_result.get("dry_run_envelope_command_executed")
    )
    real_execution_enabled = bool(noop_result.get("real_execution_enabled"))
    subprocess_invoked = bool(noop_result.get("subprocess_invoked"))
    execution_performed = bool(noop_result.get("execution_performed"))
    exit_code = int(noop_result.get("exit_code", -1))
    stdout_marker_observed = "controlled-noop-ok" in str(
        noop_result.get("stdout") or ""
    )

    command = _envelope_command(noop_result)
    parse = _parse_command(command)

    promotion_reasons: list[str] = []
    if not noop_only:
        promotion_reasons.append("noop_result_not_noop_only")
    if rendered_command_executed:
        promotion_reasons.append("noop_executed_rendered_command")
    if dry_run_command_executed:
        promotion_reasons.append("noop_executed_dry_run_command")
    if real_execution_enabled:
        promotion_reasons.append("noop_enabled_real_execution")
    if not subprocess_invoked:
        promotion_reasons.append("noop_subprocess_not_invoked")
    if not execution_performed:
        promotion_reasons.append("noop_execution_not_performed")
    if exit_code != 0:
        promotion_reasons.append("noop_exit_code_not_zero")
    if not stdout_marker_observed:
        promotion_reasons.append("noop_stdout_marker_missing")
    if not command:
        promotion_reasons.append("missing_envelope_command")
    promotion_reasons.extend(parse["reasons"])

    read_only_candidate = not promotion_reasons
    promotion_status = "promoted" if read_only_candidate else "blocked"

    promotion_id = _stable_id(
        "replay-retry-real-read-only-promotion",
        real_execution_noop_result_id,
        real_execution_dry_run_envelope_id,
        rendered_command_id,
        command,
    )

    payload = {
        "real_execution_read_only_promotion_id": promotion_id,
        "real_execution_noop_result_id": real_execution_noop_result_id,
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
        "promotion_status": promotion_status,
        "read_only_candidate": read_only_candidate,
        "read_only_module": parse["module"],
        "read_only_command": command,
        "read_only_argv": parse["argv"],
        "command_parse_valid": bool(parse["valid"]),
        "stdout_marker_observed": stdout_marker_observed,
        "noop_exit_code": exit_code,
        "noop_only": noop_only,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "reason": "real_execution_read_only_promotion_recorded",
        "reasons": promotion_reasons,
    }

    return {
        "type": REAL_READ_ONLY_PROMOTION_TYPE,
        "real_execution_read_only_promotion_id": promotion_id,
        "real_execution_noop_result_id": real_execution_noop_result_id,
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
        "promotion_status": promotion_status,
        "read_only_candidate": read_only_candidate,
        "read_only_module": parse["module"],
        "read_only_command": command,
        "read_only_argv": parse["argv"],
        "command_parse_valid": bool(parse["valid"]),
        "stdout_marker_observed": stdout_marker_observed,
        "noop_exit_code": exit_code,
        "noop_only": noop_only,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "reason": "real_execution_read_only_promotion_recorded",
        "reasons": promotion_reasons,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    real_execution_noop_result_id: str,
    rendered_command_id: str,
) -> bool:
    if (
        real_execution_noop_result_id
        and _clean(record.get("real_execution_noop_result_id"))
        != real_execution_noop_result_id
    ):
        return False
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    return True


def _find_existing_promotion(
    records: list[Mapping[str, Any]],
    *,
    real_execution_noop_result_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_READ_ONLY_PROMOTION_TYPE:
            continue
        if (
            _clean(item.get("real_execution_noop_result_id"))
            == real_execution_noop_result_id
        ):
            return item
    return None


async def build_real_execution_read_only_promotions(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish read-only promotion records from noop results exactly once."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or (
        "real-execution-read-only-promotion"
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    real_execution_noop_result_id = _clean(
        getattr(args, "real_execution_noop_result_id", "")
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    noop_results = [
        item
        for item in records
        if item.get("type") == "replay_lifecycle_retry_real_execution_noop_result"
        and _matches_filters(
            item,
            real_execution_noop_result_id=real_execution_noop_result_id,
            rendered_command_id=rendered_command_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for noop_result in noop_results:
        current_noop_result_id = _clean(noop_result.get("real_execution_noop_result_id"))

        if _find_existing_promotion(
            records,
            real_execution_noop_result_id=current_noop_result_id,
        ):
            logger.info(
                "Skipping duplicate real execution read-only promotion: noop_result_id=%s",
                current_noop_result_id,
            )
            continue

        record = build_real_execution_read_only_promotion_record(
            noop_result,
            source=source,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution read-only promotion: promotion_id=%s status=%s read_only_candidate=%s",
            record.get("real_execution_read_only_promotion_id"),
            record.get("promotion_status"),
            record.get("read_only_candidate"),
        )

    logger.info(
        "Real execution read-only promotion builder completed: promotions=%s",
        len(results),
    )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build no-execution read-only evidence command promotion records.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--rendered-command-id", default="")
    parser.add_argument("--real-execution-noop-result-id", default="")
    parser.add_argument("--source", default="real-execution-read-only-promotion")
    parser.add_argument("--json", action="store_true")
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    results = await build_real_execution_read_only_promotions(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Real execution read-only promotion builder completed: "
            f"promotions={len(results)}"
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()