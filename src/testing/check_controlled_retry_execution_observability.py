"""Read-only observability check for controlled retry execution results."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.security.runtime_validation import (
    build_security_validation_heartbeat_metrics,
)
from swarm_config import config

logger = logging.getLogger(__name__)

CONTROLLED_RESULT_TYPE = "replay_lifecycle_retry_controlled_execution_result"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _record_matches(
    record: Mapping[str, Any],
    *,
    rendered_command_id: str = "",
    plan_id: str = "",
    proposal_id: str = "",
) -> bool:
    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if rendered_command_id:
        if (
            str(record.get("rendered_command_id") or "").strip() != rendered_command_id
            and str(payload_mapping.get("rendered_command_id") or "").strip()
            != rendered_command_id
        ):
            return False

    if plan_id:
        if (
            str(record.get("plan_id") or "").strip() != plan_id
            and str(payload_mapping.get("plan_id") or "").strip() != plan_id
        ):
            return False

    if proposal_id:
        if (
            str(record.get("proposal_id") or "").strip() != proposal_id
            and str(payload_mapping.get("proposal_id") or "").strip() != proposal_id
        ):
            return False

    return True


def _build_checks(
    *,
    records: list[Mapping[str, Any]],
    metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    statuses = _safe_mapping(
        metrics.get("security_validation_controlled_execution_result_statuses")
    )
    reasons = _safe_mapping(
        metrics.get("security_validation_controlled_execution_result_reasons")
    )
    record_type_counts = _safe_mapping(metrics.get("security_validation_record_type_counts"))

    rejected = _safe_int(statuses.get("rejected"), 0)
    not_implemented = _safe_int(reasons.get("controlled_execution_not_implemented"), 0)
    security_count = _safe_int(
        record_type_counts.get(CONTROLLED_RESULT_TYPE),
        0,
    )

    payload_executed_count = 0
    operator_authorized_count = 0
    allowlist_matched_count = 0

    for record in records:
        payload = record.get("payload")
        payload_mapping = payload if isinstance(payload, Mapping) else {}

        if bool(payload_mapping.get("executed")):
            payload_executed_count += 1
        if bool(record.get("operator_authorized")):
            operator_authorized_count += 1
        if bool(record.get("allowlist_matched")):
            allowlist_matched_count += 1

    return [
        {
            "name": "controlled_execution_result_exists",
            "status": "passed" if records else "failed",
            "value": len(records),
        },
        {
            "name": "controlled_execution_result_rejected",
            "status": "passed" if rejected > 0 else "failed",
            "value": rejected,
        },
        {
            "name": "controlled_execution_not_implemented_reason",
            "status": "passed" if not_implemented > 0 else "failed",
            "value": not_implemented,
        },
        {
            "name": "controlled_execution_payload_not_executed",
            "status": "passed" if payload_executed_count == 0 else "failed",
            "value": payload_executed_count,
        },
        {
            "name": "controlled_execution_operator_not_authorized",
            "status": "passed" if operator_authorized_count == 0 else "failed",
            "value": operator_authorized_count,
        },
        {
            "name": "controlled_execution_allowlist_match_does_not_execute",
            "status": "passed" if payload_executed_count == 0 else "failed",
            "value": {
                "allowlist_matched": allowlist_matched_count,
                "payload_executed": payload_executed_count,
            },
        },
        {
            "name": "security_validates_controlled_execution_result",
            "status": "passed" if security_count > 0 else "failed",
            "value": security_count,
        },
    ]


def check_controlled_retry_execution_observability_from_records(
    records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    controlled_records = [
        record
        for record in records
        if isinstance(record, Mapping)
        and record.get("type") == CONTROLLED_RESULT_TYPE
    ]

    metrics = build_security_validation_heartbeat_metrics(controlled_records)
    checks = _build_checks(records=controlled_records, metrics=metrics)
    failed_checks = [item for item in checks if item.get("status") != "passed"]

    statuses = _safe_mapping(
        metrics.get("security_validation_controlled_execution_result_statuses")
    )
    reasons = _safe_mapping(
        metrics.get("security_validation_controlled_execution_result_reasons")
    )
    record_type_counts = _safe_mapping(metrics.get("security_validation_record_type_counts"))

    return {
        "type": "controlled_retry_execution_observability",
        "status": "passed" if not failed_checks else "failed",
        "controlled_execution_observed": bool(controlled_records),
        "controlled_execution_results": _safe_int(
            record_type_counts.get(CONTROLLED_RESULT_TYPE),
            0,
        ),
        "controlled_execution_rejected": _safe_int(statuses.get("rejected"), 0),
        "controlled_execution_skipped": _safe_int(statuses.get("skipped"), 0),
        "controlled_execution_executed": _safe_int(statuses.get("executed"), 0),
        "controlled_execution_not_implemented": _safe_int(
            reasons.get("controlled_execution_not_implemented"),
            0,
        ),
        "controlled_execution_enabled": False,
        "checks": checks,
        "failed_checks": [str(item.get("name")) for item in failed_checks],
        "brief_key_metrics": {
            "security_controlled_execution_results": _safe_int(
                record_type_counts.get(CONTROLLED_RESULT_TYPE),
                0,
            ),
            "security_controlled_execution_rejected": _safe_int(
                statuses.get("rejected"),
                0,
            ),
            "security_controlled_execution_skipped": _safe_int(
                statuses.get("skipped"),
                0,
            ),
            "security_controlled_execution_executed": _safe_int(
                statuses.get("executed"),
                0,
            ),
            "security_controlled_execution_not_implemented": _safe_int(
                reasons.get("controlled_execution_not_implemented"),
                0,
            ),
        },
    }


def check_controlled_retry_execution_observability(
    args: argparse.Namespace,
) -> dict[str, Any]:
    db_path = str(args.db_path or config.crdt_db_path)
    rendered_command_id = str(getattr(args, "rendered_command_id", "") or "").strip()
    plan_id = str(getattr(args, "plan_id", "") or "").strip()
    proposal_id = str(getattr(args, "proposal_id", "") or "").strip()

    crdt = CRDTAdapter(
        node_id="controlled-retry-execution-observability-reader",
        db_path=db_path,
    )
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        records = [
            item
            for item in state.values()
            if isinstance(item, Mapping)
            and item.get("type") == CONTROLLED_RESULT_TYPE
            and _record_matches(
                item,
                rendered_command_id=rendered_command_id,
                plan_id=plan_id,
                proposal_id=proposal_id,
            )
        ]

        return check_controlled_retry_execution_observability_from_records(records)
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def _format_result(result: Mapping[str, Any]) -> str:
    failed = result.get("failed_checks")
    failed_checks = failed if isinstance(failed, list) and failed else ["none"]

    return (
        "Controlled retry execution observability: "
        f"status={result.get('status')} "
        f"controlled_execution_observed="
        f"{str(bool(result.get('controlled_execution_observed'))).lower()} "
        f"controlled_execution_results={result.get('controlled_execution_results', 0)} "
        f"rejected={result.get('controlled_execution_rejected', 0)} "
        f"skipped={result.get('controlled_execution_skipped', 0)} "
        f"executed={result.get('controlled_execution_executed', 0)} "
        f"controlled_execution_not_implemented="
        f"{result.get('controlled_execution_not_implemented', 0)} "
        f"controlled_execution_enabled="
        f"{str(bool(result.get('controlled_execution_enabled'))).lower()} "
        f"failed_checks={','.join(str(item) for item in failed_checks)} "
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check controlled retry execution result observability.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Optional rendered command id filter.",
    )
    parser.add_argument(
        "--plan-id",
        default="",
        help="Optional plan id filter.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Optional proposal id filter.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result.",
    )
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    result = check_controlled_retry_execution_observability(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()