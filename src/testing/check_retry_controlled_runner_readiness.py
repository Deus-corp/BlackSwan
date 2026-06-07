"""Read-only readiness check before any controlled retry runner exists."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.testing.check_retry_governance_observability import (
    _exit_code_for_result as observability_exit_code,
    check_retry_governance_observability,
)
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary as trail_exit_code,
    inspect_retry_governance_trail,
)
from swarm_config import config

logger = logging.getLogger(__name__)


REQUIRED_STAGE_COUNT_KEYS = (
    "proposals",
    "approvals",
    "plans",
    "rendered_commands",
    "rendered_command_results",
    "eligibilities",
    "results",
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _count(summary: Mapping[str, Any], key: str) -> int:
    return _safe_int(_safe_mapping(summary.get("counts")).get(key), 0)


def _metric(observability: Mapping[str, Any], key: str) -> int:
    return _safe_int(_safe_mapping(observability.get("brief_key_metrics")).get(key), 0)


def _build_checks(
    *,
    trail_summary: Mapping[str, Any],
    observability: Mapping[str, Any],
) -> list[dict[str, Any]]:
    counts = _safe_mapping(trail_summary.get("counts"))
    eligibility_statuses = _safe_mapping(trail_summary.get("eligibility_statuses"))
    result_statuses = _safe_mapping(trail_summary.get("result_statuses"))
    rendered_result_statuses = _safe_mapping(
        trail_summary.get("rendered_command_result_statuses")
    )
    metrics = _safe_mapping(observability.get("brief_key_metrics"))

    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "trail_chain_complete",
            "status": "passed" if bool(trail_summary.get("chain_complete")) else "failed",
            "value": bool(trail_summary.get("chain_complete")),
        }
    )

    for key in REQUIRED_STAGE_COUNT_KEYS:
        checks.append(
            {
                "name": f"trail_has_{key}",
                "status": "passed" if _safe_int(counts.get(key), 0) > 0 else "failed",
                "value": _safe_int(counts.get(key), 0),
            }
        )

    checks.append(
        {
            "name": "rendered_command_result_is_skipped",
            "status": (
                "passed"
                if _safe_int(rendered_result_statuses.get("skipped"), 0) > 0
                else "failed"
            ),
            "value": dict(rendered_result_statuses),
        }
    )

    checks.append(
        {
            "name": "execution_eligibility_is_blocked",
            "status": (
                "passed"
                if _safe_int(eligibility_statuses.get("blocked"), 0) > 0
                else "failed"
            ),
            "value": dict(eligibility_statuses),
        }
    )

    checks.append(
        {
            "name": "execution_result_is_skipped",
            "status": (
                "passed"
                if _safe_int(result_statuses.get("skipped"), 0) > 0
                else "failed"
            ),
            "value": dict(result_statuses),
        }
    )

    checks.append(
        {
            "name": "observability_passed",
            "status": "passed" if observability.get("status") == "passed" else "failed",
            "value": observability.get("status"),
        }
    )

    checks.append(
        {
            "name": "brief_surfaces_rendered_command_result",
            "status": (
                "passed"
                if _safe_int(metrics.get("security_retry_rendered_command_results"), 0) > 0
                else "failed"
            ),
            "value": _safe_int(metrics.get("security_retry_rendered_command_results"), 0),
        }
    )

    checks.append(
        {
            "name": "brief_surfaces_execution_eligibility",
            "status": (
                "passed"
                if _safe_int(metrics.get("security_retry_execution_eligibilities"), 0) > 0
                else "failed"
            ),
            "value": _safe_int(metrics.get("security_retry_execution_eligibilities"), 0),
        }
    )

    checks.append(
        {
            "name": "brief_surfaces_execution_blocked",
            "status": (
                "passed"
                if _safe_int(metrics.get("security_retry_execution_blocked"), 0) > 0
                else "failed"
            ),
            "value": _safe_int(metrics.get("security_retry_execution_blocked"), 0),
        }
    )

    checks.append(
        {
            "name": "no_security_validation_failures",
            "status": (
                "passed"
                if _safe_int(metrics.get("security_validation_invalid_records"), 0) == 0
                and _safe_int(metrics.get("security_validation_critical_records"), 0) == 0
                else "failed"
            ),
            "value": {
                "invalid": _safe_int(metrics.get("security_validation_invalid_records"), 0),
                "critical": _safe_int(metrics.get("security_validation_critical_records"), 0),
            },
        }
    )

    return checks


def check_retry_controlled_runner_readiness_from_summaries(
    *,
    trail_summary: Mapping[str, Any],
    observability: Mapping[str, Any],
) -> dict[str, Any]:
    checks = _build_checks(
        trail_summary=trail_summary,
        observability=observability,
    )
    failed_checks = [item for item in checks if item.get("status") != "passed"]
    passed = len(checks) - len(failed_checks)
    score = round((passed / len(checks)) * 100) if checks else 0

    return {
        "type": "retry_controlled_runner_readiness",
        "status": "passed" if not failed_checks else "failed",
        "readiness_score": score,
        "checks": checks,
        "failed_checks": [str(item.get("name")) for item in failed_checks],
        "chain_complete": bool(trail_summary.get("chain_complete")),
        "observability_status": observability.get("status"),
        "controlled_execution_enabled": False,
        "recommendation": (
            "ready_for_controlled_runner_design"
            if not failed_checks
            else "complete_safe_retry_governance_baseline_first"
        ),
    }


def check_retry_controlled_runner_readiness(args: argparse.Namespace) -> dict[str, Any]:
    db_path = str(args.db_path or config.crdt_db_path)
    proposal_id = str(getattr(args, "proposal_id", "") or "").strip()

    trail_summary = inspect_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            approval_id="",
            plan_id="",
        )
    )
    observability = check_retry_governance_observability(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            json=False,
        )
    )

    result = check_retry_controlled_runner_readiness_from_summaries(
        trail_summary=trail_summary,
        observability=observability,
    )
    result["exit_codes"] = {
        "trail": trail_exit_code(trail_summary, require_complete=True),
        "observability": observability_exit_code(observability),
    }
    return result


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def _format_result(result: Mapping[str, Any]) -> str:
    return (
        "Retry controlled runner readiness: "
        f"status={result.get('status')} "
        f"readiness_score={result.get('readiness_score')} "
        f"chain_complete={str(bool(result.get('chain_complete'))).lower()} "
        f"observability={result.get('observability_status')} "
        f"controlled_execution_enabled={str(bool(result.get('controlled_execution_enabled'))).lower()} "
        f"failed_checks={','.join(result.get('failed_checks') or ['none'])} "
        f"recommendation={result.get('recommendation')} "
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only readiness check for future controlled retry runner.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
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
    result = check_retry_controlled_runner_readiness(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()