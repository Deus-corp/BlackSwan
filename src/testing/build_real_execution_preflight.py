"""Build read-only real execution preflight records for controlled retry commands.

This module never invokes subprocesses. It records whether a future real
execution request satisfies the preflight contract, while keeping real execution
unsupported and blocked.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.testing.controlled_retry_command_allowlist import (
    parse_controlled_retry_command,
)
from src.testing.controlled_retry_execution_adapter import (
    describe_controlled_retry_execution_adapter_contract,
)
from swarm_config import config

logger = logging.getLogger(__name__)

REAL_PREFLIGHT_TYPE = "replay_lifecycle_retry_real_execution_preflight"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_clean(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_real_execution_preflight_record(
    controlled_result: Mapping[str, Any],
    *,
    source: str = "real-execution-preflight",
    require_real_execution_request: bool = True,
) -> dict[str, Any]:
    """Build a fail-closed real execution preflight record."""
    controlled_execution_result_id = _clean(
        controlled_result.get("controlled_execution_result_id")
    )
    rendered_command_id = _clean(controlled_result.get("rendered_command_id"))
    plan_id = _clean(controlled_result.get("plan_id"))
    proposal_id = _clean(controlled_result.get("proposal_id"))
    approval_id = _clean(controlled_result.get("approval_id"))
    command = _clean(controlled_result.get("command"))
    timeout_profile = _clean(controlled_result.get("timeout_profile")) or "standard"
    decision_mode = _clean(controlled_result.get("decision_mode")) or "manual"

    if not controlled_execution_result_id:
        raise ValueError("controlled_execution_result_id is required")
    if not rendered_command_id:
        raise ValueError("rendered_command_id is required")

    command_parse = controlled_result.get("command_parse")
    if not isinstance(command_parse, Mapping):
        command_parse = parse_controlled_retry_command(command)

    adapter_contract = describe_controlled_retry_execution_adapter_contract()
    real_adapter_contract = adapter_contract.get("real_adapter_contract")
    real_adapter_mapping = (
        real_adapter_contract if isinstance(real_adapter_contract, Mapping) else {}
    )

    real_execution_requested = bool(
        controlled_result.get("real_execution_requested")
    )
    operator_authorized = bool(controlled_result.get("operator_authorized"))
    allowlist_matched = bool(controlled_result.get("allowlist_matched"))
    command_parse_valid = bool(
        command_parse.get("valid") if isinstance(command_parse, Mapping) else False
    )
    command_parse_allowlist_matched = bool(
        command_parse.get("allowlist_matched")
        if isinstance(command_parse, Mapping)
        else False
    )

    reasons: list[str] = []
    if require_real_execution_request and not real_execution_requested:
        reasons.append("real_execution_request_missing")
    if not operator_authorized:
        reasons.append("operator_authorization_missing")
    if not allowlist_matched:
        reasons.append("command_not_allowlisted")
    if not command_parse_valid:
        reasons.append("command_parse_invalid")
    if not command_parse_allowlist_matched:
        reasons.append("command_parse_not_allowlisted")
    if adapter_contract.get("real_execution_supported") is not True:
        reasons.append("real_execution_not_supported")
    if adapter_contract.get("subprocess_supported") is not True:
        reasons.append("subprocess_not_supported")
    if real_adapter_mapping.get("runnable") is not True:
        reasons.append("real_adapter_not_runnable")
    if real_adapter_mapping.get("requires_explicit_pr") is True:
        reasons.append("real_adapter_requires_explicit_pr")

    # Until a separate implementation PR exists, preflight always blocks.
    status = "blocked"
    would_execute = False
    execution_performed = False
    subprocess_invoked = False

    preflight_id = _stable_id(
        "replay-retry-real-preflight",
        controlled_execution_result_id,
        rendered_command_id,
        plan_id,
    )

    payload = {
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": status,
        "reason": reasons[0] if reasons else "real_execution_not_supported",
        "reasons": reasons,
        "real_execution_requested": real_execution_requested,
        "operator_authorized": operator_authorized,
        "allowlist_matched": allowlist_matched,
        "command_parse_valid": command_parse_valid,
        "command_parse_allowlist_matched": command_parse_allowlist_matched,
        "would_execute": would_execute,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "real_execution_supported": bool(
            adapter_contract.get("real_execution_supported")
        ),
        "subprocess_supported": bool(adapter_contract.get("subprocess_supported")),
        "real_adapter_runnable": bool(real_adapter_mapping.get("runnable")),
        "real_adapter_requires_explicit_pr": bool(
            real_adapter_mapping.get("requires_explicit_pr")
        ),
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "command_parse": dict(command_parse) if isinstance(command_parse, Mapping) else {},
        "adapter_contract": adapter_contract,
    }

    return {
        "type": REAL_PREFLIGHT_TYPE,
        "real_execution_preflight_id": preflight_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": status,
        "reason": payload["reason"],
        "reasons": reasons,
        "real_execution_requested": real_execution_requested,
        "operator_authorized": operator_authorized,
        "allowlist_matched": allowlist_matched,
        "command_parse_valid": command_parse_valid,
        "command_parse_allowlist_matched": command_parse_allowlist_matched,
        "would_execute": would_execute,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "real_execution_supported": payload["real_execution_supported"],
        "subprocess_supported": payload["subprocess_supported"],
        "real_adapter_runnable": payload["real_adapter_runnable"],
        "real_adapter_requires_explicit_pr": payload[
            "real_adapter_requires_explicit_pr"
        ],
        "timeout_profile": timeout_profile,
        "decision_mode": decision_mode,
        "command": command,
        "source": source,
        "payload": payload,
    }


def _matches_filters(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str,
    controlled_execution_result_id: str,
) -> bool:
    if rendered_command_id and _clean(record.get("rendered_command_id")) != rendered_command_id:
        return False
    if (
        controlled_execution_result_id
        and _clean(record.get("controlled_execution_result_id"))
        != controlled_execution_result_id
    ):
        return False
    return True


def _find_existing_preflight(
    records: list[Mapping[str, Any]],
    *,
    controlled_execution_result_id: str,
    rendered_command_id: str,
) -> Mapping[str, Any] | None:
    for item in records:
        if item.get("type") != REAL_PREFLIGHT_TYPE:
            continue
        if (
            _clean(item.get("controlled_execution_result_id"))
            == controlled_execution_result_id
            and _clean(item.get("rendered_command_id")) == rendered_command_id
        ):
            return item
    return None


async def build_real_execution_preflights(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish real execution preflight records for controlled results."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = _clean(getattr(args, "source", "")) or "real-execution-preflight"
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    controlled_execution_result_id = _clean(
        getattr(args, "controlled_execution_result_id", "")
    )
    require_real_execution_request = bool(
        getattr(args, "require_real_execution_request", True)
    )

    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    records = [item for item in state.values() if isinstance(item, Mapping)]

    controlled_results = [
        item
        for item in records
        if item.get("type") == "replay_lifecycle_retry_controlled_execution_result"
        and _matches_filters(
            item,
            rendered_command_id=rendered_command_id,
            controlled_execution_result_id=controlled_execution_result_id,
        )
    ]

    results: list[dict[str, Any]] = []
    for controlled_result in controlled_results:
        current_controlled_result_id = _clean(
            controlled_result.get("controlled_execution_result_id")
        )
        current_rendered_command_id = _clean(controlled_result.get("rendered_command_id"))

        if _find_existing_preflight(
            records,
            controlled_execution_result_id=current_controlled_result_id,
            rendered_command_id=current_rendered_command_id,
        ):
            logger.info(
                "Skipping duplicate real execution preflight: controlled_execution_result_id=%s rendered_command_id=%s",
                current_controlled_result_id,
                current_rendered_command_id,
            )
            continue

        record = build_real_execution_preflight_record(
            controlled_result,
            source=source,
            require_real_execution_request=require_real_execution_request,
        )
        await crdt.add_genome(record)
        records.append(record)
        results.append(record)
        logger.info(
            "Published real execution preflight: controlled_execution_result_id=%s status=%s reason=%s",
            record.get("controlled_execution_result_id"),
            record.get("status"),
            record.get("reason"),
        )

    logger.info("Real execution preflight builder completed: preflights=%s", len(results))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build fail-closed real execution preflight records.",
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
        "--controlled-execution-result-id",
        default="",
        help="Controlled execution result id filter.",
    )
    parser.add_argument(
        "--source",
        default="real-execution-preflight",
        help="CRDT source/node id.",
    )
    parser.add_argument(
        "--allow-missing-real-execution-request",
        action="store_true",
        help="Allow preflight records for controlled results without real_execution_requested=true.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON records.",
    )
    return parser


async def _async_main() -> None:
    args = build_parser().parse_args()
    args.require_real_execution_request = not bool(
        getattr(args, "allow_missing_real_execution_request", False)
    )
    results = await build_real_execution_preflights(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(f"Real execution preflight builder completed: preflights={len(results)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()