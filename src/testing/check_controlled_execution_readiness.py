"""Final pre-execution readiness report for controlled retry execution.

This helper is read-only. It aggregates the safe retry governance trail,
controlled execution observability, and controlled gate state before any
execution adapter is introduced.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.testing.check_controlled_retry_execution_observability import (
    _exit_code_for_result as controlled_observability_exit_code,
    check_controlled_retry_execution_observability,
)
from src.testing.check_retry_governance_observability import (
    _exit_code_for_result as retry_observability_exit_code,
    check_retry_governance_observability,
)
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary as trail_exit_code,
    inspect_retry_governance_trail,
)
from swarm_config import config

logger = logging.getLogger(__name__)


def check_controlled_execution_readiness(args: argparse.Namespace) -> dict[str, Any]:
    """Build a read-only final pre-execution readiness report."""
    db_path = str(args.db_path or config.crdt_db_path)
    proposal_id = str(getattr(args, "proposal_id", "") or "").strip()
    rendered_command_id = str(getattr(args, "rendered_command_id", "") or "").strip()
    require_operator_authorized = bool(
        getattr(args, "require_operator_authorized", False)
    )

    trail_summary = inspect_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            approval_id="",
            plan_id="",
        )
    )
    retry_observability = check_retry_governance_observability(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            json=False,
        )
    )
    controlled_observability = check_controlled_retry_execution_observability(
        argparse.Namespace(
            db_path=db_path,
            rendered_command_id=rendered_command_id,
            plan_id="",
            proposal_id=proposal_id,
            json=False,
        )
    )

    checks = _build_checks(
        trail_summary=trail_summary,
        retry_observability=retry_observability,
        controlled_observability=controlled_observability,
        require_operator_authorized=require_operator_authorized,
    )
    failed_checks = [item for item in checks if item.get("status") != "passed"]

    ready_for_mock_execution = not failed_checks
    ready_for_real_execution = False

    blocking_reasons = [str(item.get("name")) for item in failed_checks]
    if ready_for_mock_execution:
        blocking_reasons.append("real_execution_not_supported_yet")

    return {
        "type": "controlled_execution_readiness_report",
        "status": "passed" if ready_for_mock_execution else "failed",
        "ready_for_mock_execution": ready_for_mock_execution,
        "ready_for_real_execution": ready_for_real_execution,
        "blocking_reasons": blocking_reasons,
        "require_operator_authorized": require_operator_authorized,
        "proposal_id": proposal_id or None,
        "rendered_command_id": rendered_command_id or None,
        "trail_summary": trail_summary,
        "retry_observability": retry_observability,
        "controlled_observability": controlled_observability,
        "checks": checks,
        "exit_codes": {
            "trail": trail_exit_code(trail_summary, require_complete=True),
            "retry_observability": retry_observability_exit_code(retry_observability),
            "controlled_observability": controlled_observability_exit_code(
                controlled_observability
            ),
            "real_execution": 1,
        },
    }


def _build_checks(
    *,
    trail_summary: Mapping[str, Any],
    retry_observability: Mapping[str, Any],
    controlled_observability: Mapping[str, Any],
    require_operator_authorized: bool,
) -> list[dict[str, Any]]:
    counts = _safe_mapping(trail_summary.get("counts"))
    controlled_statuses = _safe_mapping(
        trail_summary.get("controlled_execution_result_statuses")
    )
    controlled_reasons = _safe_mapping(
        trail_summary.get("controlled_execution_result_reasons")
    )
    command_parse_valid = _safe_mapping(
        trail_summary.get("controlled_command_parse_valid")
    )
    command_parse_allowlisted = _safe_mapping(
        trail_summary.get("controlled_command_parse_allowlist_matched")
    )
    command_parse_execution_performed = _safe_mapping(
        trail_summary.get("controlled_command_parse_execution_performed")
    )
    operator_authorized = _safe_mapping(
        trail_summary.get("controlled_execution_operator_authorized")
    )
    gate_statuses = _safe_mapping(trail_summary.get("controlled_gate_statuses"))
    gate_would_execute = _safe_mapping(
        trail_summary.get("controlled_gate_would_execute")
    )
    gate_execution_performed = _safe_mapping(
        trail_summary.get("controlled_gate_execution_performed")
    )
    gate_reasons = _safe_mapping(trail_summary.get("controlled_gate_reasons"))

    checks = [
        _check(
            "trail_chain_complete",
            bool(trail_summary.get("chain_complete")),
            bool(trail_summary.get("chain_complete")),
        ),
        _check(
            "trail_has_controlled_execution_result",
            _safe_int(counts.get("controlled_execution_results")) > 0,
            _safe_int(counts.get("controlled_execution_results")),
        ),
        _check(
            "controlled_result_rejected",
            _safe_int(controlled_statuses.get("rejected")) > 0,
            _safe_int(controlled_statuses.get("rejected")),
        ),
        _check(
            "controlled_result_not_implemented",
            _safe_int(controlled_reasons.get("controlled_execution_not_implemented"))
            > 0,
            _safe_int(controlled_reasons.get("controlled_execution_not_implemented")),
        ),
        _check(
            "command_parse_valid",
            _safe_int(command_parse_valid.get("true")) > 0,
            _safe_int(command_parse_valid.get("true")),
        ),
        _check(
            "command_parse_allowlisted",
            _safe_int(command_parse_allowlisted.get("true")) > 0,
            _safe_int(command_parse_allowlisted.get("true")),
        ),
        _check(
            "command_parse_did_not_execute",
            _safe_int(command_parse_execution_performed.get("true")) == 0,
            _safe_int(command_parse_execution_performed.get("true")),
        ),
        _check(
            "controlled_gate_blocked",
            _safe_int(gate_statuses.get("blocked")) > 0,
            _safe_int(gate_statuses.get("blocked")),
        ),
        _check(
            "controlled_gate_would_not_execute",
            _safe_int(gate_would_execute.get("true")) == 0,
            _safe_int(gate_would_execute.get("true")),
        ),
        _check(
            "controlled_gate_did_not_execute",
            _safe_int(gate_execution_performed.get("true")) == 0,
            _safe_int(gate_execution_performed.get("true")),
        ),
        _check(
            "controlled_gate_not_enabled_reason_observed",
            _safe_int(gate_reasons.get("controlled_execution_not_enabled")) > 0,
            _safe_int(gate_reasons.get("controlled_execution_not_enabled")),
        ),
        _check(
            "retry_observability_passed",
            retry_observability.get("status") == "passed",
            retry_observability.get("status"),
        ),
        _check(
            "controlled_observability_passed",
            controlled_observability.get("status") == "passed",
            controlled_observability.get("status"),
        ),
        _check(
            "controlled_observability_reports_no_execution",
            _safe_int(
                controlled_observability.get(
                    "controlled_execution_gate_execution_performed"
                )
            )
            == 0
            and _safe_int(controlled_observability.get("controlled_execution_executed"))
            == 0,
            {
                "gate_execution_performed": controlled_observability.get(
                    "controlled_execution_gate_execution_performed"
                ),
                "controlled_execution_executed": controlled_observability.get(
                    "controlled_execution_executed"
                ),
            },
        ),
    ]

    operator_authorized_count = _safe_int(operator_authorized.get("true"))
    if require_operator_authorized:
        checks.append(
            _check(
                "operator_authorized",
                operator_authorized_count > 0,
                operator_authorized_count,
            )
        )
    else:
        checks.append(
            _check(
                "operator_authorization_optional",
                True,
                operator_authorized_count,
            )
        )

    return checks


def _check(name: str, passed: bool, value: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "value": value,
    }


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def _format_result(result: Mapping[str, Any]) -> str:
    failed = result.get("blocking_reasons")
    blocking_reasons = failed if isinstance(failed, list) and failed else ["none"]

    return (
        "Controlled execution readiness: "
        f"status={result.get('status')} "
        f"ready_for_mock_execution="
        f"{str(bool(result.get('ready_for_mock_execution'))).lower()} "
        f"ready_for_real_execution="
        f"{str(bool(result.get('ready_for_real_execution'))).lower()} "
        f"require_operator_authorized="
        f"{str(bool(result.get('require_operator_authorized'))).lower()} "
        f"blocking_reasons={','.join(str(item) for item in blocking_reasons)} "
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check controlled execution readiness before any execution adapter.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Retry governance proposal id filter.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Controlled rendered command id filter.",
    )
    parser.add_argument(
        "--require-operator-authorized",
        action="store_true",
        help="Require operator_authorized=true for mock execution readiness.",
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
    result = check_controlled_execution_readiness(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()