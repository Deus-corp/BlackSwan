"""Verify the controlled retry and guarded repair golden path.

This smoke entrypoint is verification-only:
- reads existing CRDT records,
- builds the retry governance trail summary,
- verifies the guarded repair + post-repair evidence milestone,
- does not publish new CRDT records,
- does not run repair/evidence subprocesses,
- does not enable arbitrary real execution.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping
from typing import Any

from src.core.crdt_adapter import CRDTAdapter
from src.testing.inspect_retry_governance_trail import (
    inspect_retry_governance_trail_from_records,
)
from swarm_config import config

logger = logging.getLogger(__name__)

GOLDEN_PATH_SCHEMA_VERSION = "controlled-retry-guarded-repair-golden-path/v1"

POST_REPAIR_CLOSE_LOOP_ACTION = "close_repair_loop"


REQUIRED_TYPE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("retry proposal", ("replay_lifecycle_retry_proposal",)),
    ("retry approval", ("replay_lifecycle_retry_approval",)),
    ("retry execution plan", ("replay_lifecycle_retry_execution_plan",)),
    ("retry rendered command", ("replay_lifecycle_retry_rendered_command",)),
    (
        "retry rendered command result",
        ("replay_lifecycle_retry_rendered_command_result",),
    ),
    ("retry execution eligibility", ("replay_lifecycle_retry_execution_eligibility",)),
    ("retry execution result", ("replay_lifecycle_retry_execution_result",)),
    (
        "controlled execution result",
        ("replay_lifecycle_retry_controlled_execution_result",),
    ),
    ("real execution preflight", ("replay_lifecycle_retry_real_execution_preflight",)),
    ("real execution approval", ("replay_lifecycle_retry_real_execution_approval",)),
    (
        "real execution approval transition",
        ("replay_lifecycle_retry_real_execution_approval_transition",),
    ),
    (
        "real execution final gate",
        ("replay_lifecycle_retry_real_execution_final_gate",),
    ),
    (
        "real execution dry-run envelope",
        ("replay_lifecycle_retry_real_execution_dry_run_envelope",),
    ),
    (
        "real execution noop result",
        ("replay_lifecycle_retry_real_execution_noop_result",),
    ),
    (
        "read-only promotion",
        ("replay_lifecycle_retry_real_execution_read_only_promotion",),
    ),
    (
        "read-only final gate",
        ("replay_lifecycle_retry_real_execution_read_only_final_gate",),
    ),
    (
        "read-only approval",
        ("replay_lifecycle_retry_real_execution_read_only_approval",),
    ),
    (
        "read-only approval transition",
        ("replay_lifecycle_retry_real_execution_read_only_approval_transition",),
    ),
    (
        "read-only readiness gate",
        ("replay_lifecycle_retry_real_execution_read_only_readiness_gate",),
    ),
    (
        "guarded read-only execution result",
        (
            "replay_lifecycle_retry_real_execution_read_only_execution_result",
            "replay_lifecycle_retry_guarded_read_only_execution_result",
        ),
    ),
    (
        "read-only feedback",
        ("replay_lifecycle_retry_real_execution_read_only_feedback",),
    ),
    (
        "repair plan",
        ("replay_lifecycle_retry_real_execution_read_only_repair_plan",),
    ),
    (
        "repair action bundle",
        ("replay_lifecycle_retry_real_execution_read_only_repair_action_bundle",),
    ),
    (
        "repair action bundle review",
        (
            "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review",
        ),
    ),
    (
        "repair approval",
        ("replay_lifecycle_retry_real_execution_repair_approval",),
    ),
    (
        "repair approval transition",
        ("replay_lifecycle_retry_real_execution_repair_approval_transition",),
    ),
    (
        "repair final gate",
        ("replay_lifecycle_retry_real_execution_repair_final_gate",),
    ),
    (
        "repair dry-run envelope",
        ("replay_lifecycle_retry_real_execution_repair_dry_run_envelope",),
    ),
    (
        "repair noop result",
        ("replay_lifecycle_retry_real_execution_repair_noop_result",),
    ),
    (
        "repair noop feedback",
        ("replay_lifecycle_retry_real_execution_repair_noop_feedback",),
    ),
    (
        "repair readiness gate",
        ("replay_lifecycle_retry_real_execution_repair_readiness_gate",),
    ),
    (
        "guarded repair execution result",
        ("replay_lifecycle_retry_guarded_repair_execution_result",),
    ),
    (
        "post-repair evidence check",
        ("replay_lifecycle_retry_post_repair_evidence_check",),
    ),
)


REQUIRED_LINKAGE_FLAGS: tuple[str, ...] = (
    "real_linkage_complete",
    "real_dry_run_linkage_complete",
    "real_noop_linkage_complete",
    "real_read_only_promotion_linkage_complete",
    "real_read_only_final_gate_linkage_complete",
    "real_read_only_approval_linkage_complete",
    "real_read_only_approval_transition_linkage_complete",
    "real_read_only_readiness_gate_linkage_complete",
    "real_read_only_execution_result_linkage_complete",
    "real_read_only_feedback_linkage_complete",
    "real_read_only_repair_plan_linkage_complete",
    "real_read_only_repair_action_bundle_linkage_complete",
    "real_read_only_repair_action_bundle_review_linkage_complete",
    "real_repair_approval_linkage_complete",
    "real_repair_approval_transition_linkage_complete",
    "real_repair_final_gate_linkage_complete",
    "real_repair_dry_run_envelope_linkage_complete",
    "real_repair_noop_result_linkage_complete",
    "real_repair_noop_feedback_linkage_complete",
    "real_repair_readiness_gate_linkage_complete",
    "guarded_repair_execution_linkage_complete",
    "post_repair_evidence_linkage_complete",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _counter_value(summary: Mapping[str, Any], field: str, key: str) -> int:
    return _safe_int(_safe_mapping(summary.get(field)).get(key), 0)


def _check(name: str, passed: bool, details: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "details": details,
    }


def _type_group_count(summary: Mapping[str, Any], aliases: tuple[str, ...]) -> int:
    by_type = _safe_mapping(summary.get("by_type"))
    return sum(_safe_int(by_type.get(alias), 0) for alias in aliases)


def _has_no_true(summary: Mapping[str, Any], field: str) -> bool:
    return _counter_value(summary, field, "true") == 0


def _has_one_true(summary: Mapping[str, Any], field: str) -> bool:
    return _counter_value(summary, field, "true") == 1


def _has_one_false(summary: Mapping[str, Any], field: str) -> bool:
    return _counter_value(summary, field, "false") == 1


def _filter_records_by_proposal_id(
    records: list[Mapping[str, Any]],
    *,
    proposal_id: str,
) -> list[Mapping[str, Any]]:
    clean_proposal_id = _clean(proposal_id)
    if not clean_proposal_id:
        return records

    filtered: list[Mapping[str, Any]] = []
    for item in records:
        payload = item.get("payload")
        payload_mapping = payload if isinstance(payload, Mapping) else {}

        if (
            _clean(item.get("proposal_id")) == clean_proposal_id
            or _clean(payload_mapping.get("proposal_id")) == clean_proposal_id
        ):
            filtered.append(item)

    return filtered


def _inspect_records(
    records: list[Mapping[str, Any]],
    *,
    proposal_id: str,
) -> dict[str, Any]:
    """Build governance trail summary with compatibility for older signatures."""
    try:
        return inspect_retry_governance_trail_from_records(
            records,
            proposal_id=proposal_id,
        )
    except TypeError:
        filtered = _filter_records_by_proposal_id(records, proposal_id=proposal_id)
        return inspect_retry_governance_trail_from_records(filtered)


def build_controlled_retry_guarded_repair_golden_path_report(
    trail_summary: Mapping[str, Any],
    *,
    proposal_id: str = "",
) -> dict[str, Any]:
    """Build final golden-path smoke report from a governance trail summary."""
    clean_proposal_id = _clean(proposal_id)
    checks: list[dict[str, Any]] = []

    checks.append(
        _check(
            "chain_complete",
            bool(trail_summary.get("chain_complete")),
            trail_summary.get("chain_complete"),
        )
    )
    checks.append(
        _check(
            "missing_stages_empty",
            not list(trail_summary.get("missing_stages") or []),
            trail_summary.get("missing_stages") or [],
        )
    )

    for label, aliases in REQUIRED_TYPE_GROUPS:
        count = _type_group_count(trail_summary, aliases)
        checks.append(
            _check(
                f"required_record_type_present:{label}",
                count == 1,
                {"aliases": list(aliases), "count": count},
            )
        )

    for field in REQUIRED_LINKAGE_FLAGS:
        checks.append(
            _check(
                field,
                bool(trail_summary.get(field)),
                trail_summary.get(field),
            )
        )

    checks.extend(
        [
            _check(
                "guarded_repair_execution_succeeded",
                _counter_value(
                    trail_summary,
                    "guarded_repair_execution_statuses",
                    "succeeded",
                )
                == 1,
                _safe_mapping(trail_summary.get("guarded_repair_execution_statuses")),
            ),
            _check(
                "guarded_repair_execution_allowed",
                _has_one_true(trail_summary, "guarded_repair_execution_allowed"),
                _safe_mapping(trail_summary.get("guarded_repair_execution_allowed")),
            ),
            _check(
                "guarded_repair_execution_marker_observed",
                _has_one_true(
                    trail_summary,
                    "guarded_repair_execution_marker_observed",
                ),
                _safe_mapping(
                    trail_summary.get("guarded_repair_execution_marker_observed")
                ),
            ),
            _check(
                "guarded_repair_execution_exit_code_zero",
                _counter_value(
                    trail_summary,
                    "guarded_repair_execution_exit_codes",
                    "0",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("guarded_repair_execution_exit_codes")
                ),
            ),
            _check(
                "guarded_repair_execution_target_count_9",
                _counter_value(
                    trail_summary,
                    "guarded_repair_execution_target_counts",
                    "9",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("guarded_repair_execution_target_counts")
                ),
            ),
            _check(
                "guarded_repair_execution_next_action_post_evidence",
                _counter_value(
                    trail_summary,
                    "guarded_repair_execution_next_actions",
                    "run_post_repair_evidence_check",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("guarded_repair_execution_next_actions")
                ),
            ),
            _check(
                "guarded_repair_execution_repair_actions_executed",
                _has_one_true(
                    trail_summary,
                    "guarded_repair_execution_repair_actions_executed",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "guarded_repair_execution_repair_actions_executed"
                    )
                ),
            ),
            _check(
                "guarded_repair_execution_repair_execution_enabled",
                _has_one_true(
                    trail_summary,
                    "guarded_repair_execution_repair_execution_enabled",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "guarded_repair_execution_repair_execution_enabled"
                    )
                ),
            ),
            _check(
                "guarded_repair_execution_did_not_enable_real_execution",
                _has_no_true(
                    trail_summary,
                    "guarded_repair_execution_real_execution_enabled",
                ),
                _safe_mapping(
                    trail_summary.get("guarded_repair_execution_real_execution_enabled")
                ),
            ),
            _check(
                "guarded_repair_execution_did_not_execute_rendered_command",
                _has_no_true(
                    trail_summary,
                    "guarded_repair_execution_rendered_command_executed",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "guarded_repair_execution_rendered_command_executed"
                    )
                ),
            ),
            _check(
                "guarded_repair_execution_did_not_execute_dry_run_command",
                _has_no_true(
                    trail_summary,
                    "guarded_repair_execution_dry_run_command_executed",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "guarded_repair_execution_dry_run_command_executed"
                    )
                ),
            ),
        ]
    )

    checks.extend(
        [
            _check(
                "post_repair_evidence_passed",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_statuses",
                    "passed",
                )
                == 1,
                _safe_mapping(trail_summary.get("post_repair_evidence_statuses")),
            ),
            _check(
                "post_repair_evidence_allowed",
                _has_one_true(trail_summary, "post_repair_evidence_allowed"),
                _safe_mapping(trail_summary.get("post_repair_evidence_allowed")),
            ),
            _check(
                "post_repair_evidence_enabled",
                _has_one_true(trail_summary, "post_repair_evidence_enabled"),
                _safe_mapping(trail_summary.get("post_repair_evidence_enabled")),
            ),
            _check(
                "post_repair_evidence_marker_observed",
                _has_one_true(
                    trail_summary,
                    "post_repair_evidence_marker_observed",
                ),
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_marker_observed")
                ),
            ),
            _check(
                "post_repair_evidence_exit_code_zero",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_exit_codes",
                    "0",
                )
                == 1,
                _safe_mapping(trail_summary.get("post_repair_evidence_exit_codes")),
            ),
            _check(
                "post_repair_evidence_outcome_verified",
                _has_one_true(
                    trail_summary,
                    "post_repair_evidence_outcome_verified",
                ),
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_outcome_verified")
                ),
            ),
            _check(
                "post_repair_evidence_expected_count_9",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_expected_counts",
                    "9",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_expected_counts")
                ),
            ),
            _check(
                "post_repair_evidence_verified_count_9",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_verified_counts",
                    "9",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_verified_counts")
                ),
            ),
            _check(
                "post_repair_evidence_no_missing_targets",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_missing_counts",
                    "0",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_missing_counts")
                ),
            ),
            _check(
                "post_repair_evidence_no_unexpected_targets",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_unexpected_counts",
                    "0",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_unexpected_counts")
                ),
            ),
            _check(
                "post_repair_evidence_next_action_close_loop",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_next_actions",
                    POST_REPAIR_CLOSE_LOOP_ACTION,
                )
                == 1,
                _safe_mapping(trail_summary.get("post_repair_evidence_next_actions")),
            ),
            _check(
                "post_repair_evidence_source_guarded_repair_succeeded",
                _counter_value(
                    trail_summary,
                    "post_repair_evidence_source_statuses",
                    "succeeded",
                )
                == 1,
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_source_statuses")
                ),
            ),
            _check(
                "post_repair_evidence_source_repair_execution_enabled",
                _has_one_true(
                    trail_summary,
                    "post_repair_evidence_source_repair_execution_enabled",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "post_repair_evidence_source_repair_execution_enabled"
                    )
                ),
            ),
            _check(
                "post_repair_evidence_source_did_not_enable_real_execution",
                _has_no_true(
                    trail_summary,
                    "post_repair_evidence_source_real_execution_enabled",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "post_repair_evidence_source_real_execution_enabled"
                    )
                ),
            ),
            _check(
                "post_repair_evidence_did_not_enable_repair_execution",
                _has_no_true(
                    trail_summary,
                    "post_repair_evidence_repair_execution_enabled",
                ),
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_repair_execution_enabled")
                ),
            ),
            _check(
                "post_repair_evidence_did_not_enable_real_execution",
                _has_no_true(
                    trail_summary,
                    "post_repair_evidence_real_execution_enabled",
                ),
                _safe_mapping(
                    trail_summary.get("post_repair_evidence_real_execution_enabled")
                ),
            ),
            _check(
                "post_repair_evidence_did_not_perform_repair_execution",
                _has_no_true(
                    trail_summary,
                    "post_repair_evidence_repair_execution_performed",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "post_repair_evidence_repair_execution_performed"
                    )
                ),
            ),
            _check(
                "post_repair_evidence_did_not_invoke_repair_subprocess",
                _has_no_true(
                    trail_summary,
                    "post_repair_evidence_repair_subprocess_invoked",
                ),
                _safe_mapping(
                    trail_summary.get(
                        "post_repair_evidence_repair_subprocess_invoked"
                    )
                ),
            ),
        ]
    )

    failed_checks = [item for item in checks if item.get("status") != "passed"]
    status = "passed" if not failed_checks else "failed"

    report = {
        "type": "controlled_retry_guarded_repair_golden_path_report",
        "schema_version": GOLDEN_PATH_SCHEMA_VERSION,
        "status": status,
        "golden_path_status": status,
        "proposal_id": clean_proposal_id or None,
        "checks": checks,
        "failed_checks": failed_checks,
        "failed_check_count": len(failed_checks),
        "total_check_count": len(checks),
        "chain_complete": bool(trail_summary.get("chain_complete")),
        "post_repair_status": "passed"
        if _counter_value(trail_summary, "post_repair_evidence_statuses", "passed")
        == 1
        else "not_verified",
        "repair_outcome_verified": _has_one_true(
            trail_summary,
            "post_repair_evidence_outcome_verified",
        ),
        "recommended_next_action": POST_REPAIR_CLOSE_LOOP_ACTION
        if _counter_value(
            trail_summary,
            "post_repair_evidence_next_actions",
            POST_REPAIR_CLOSE_LOOP_ACTION,
        )
        == 1
        else "unknown",
        "ready_for_real_execution": False,
        "real_execution_enabled": False,
        "summary": {
            "total_records": trail_summary.get("total_records"),
            "by_type": dict(_safe_mapping(trail_summary.get("by_type"))),
            "counts": dict(_safe_mapping(trail_summary.get("counts"))),
            "guarded_repair_execution_statuses": dict(
                _safe_mapping(trail_summary.get("guarded_repair_execution_statuses"))
            ),
            "post_repair_evidence_statuses": dict(
                _safe_mapping(trail_summary.get("post_repair_evidence_statuses"))
            ),
            "post_repair_evidence_next_actions": dict(
                _safe_mapping(trail_summary.get("post_repair_evidence_next_actions"))
            ),
            "post_repair_evidence_linkage_complete": bool(
                trail_summary.get("post_repair_evidence_linkage_complete")
            ),
            "post_repair_evidence_orphans": _safe_int(
                trail_summary.get("post_repair_evidence_orphans"), 0
            ),
        },
    }
    return report


def _format_report(report: Mapping[str, Any]) -> str:
    return (
        "Controlled retry guarded repair golden path: "
        f"status={report.get('status')} "
        f"schema_version={report.get('schema_version')} "
        f"proposal_id={report.get('proposal_id')} "
        f"chain_complete={str(bool(report.get('chain_complete'))).lower()} "
        f"post_repair_status={report.get('post_repair_status')} "
        f"repair_outcome_verified={str(bool(report.get('repair_outcome_verified'))).lower()} "
        f"recommended_next_action={report.get('recommended_next_action')} "
        f"ready_for_real_execution={str(bool(report.get('ready_for_real_execution'))).lower()} "
        f"real_execution_enabled={str(bool(report.get('real_execution_enabled'))).lower()} "
        f"failed_check_count={report.get('failed_check_count', 0)} "
        f"total_check_count={report.get('total_check_count', 0)}"
    )


def _load_records(*, db_path: str, source: str) -> list[Mapping[str, Any]]:
    crdt = CRDTAdapter(node_id=source, db_path=db_path)
    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        refresh()

    state = getattr(crdt, "state", {}) or {}
    return [item for item in state.values() if isinstance(item, Mapping)]


def run_golden_path_smoke(args: argparse.Namespace) -> dict[str, Any]:
    db_path = str(args.db_path or config.crdt_db_path)
    proposal_id = _clean(getattr(args, "proposal_id", ""))
    source = _clean(getattr(args, "source", "")) or "golden-path-smoke"

    records = _load_records(db_path=db_path, source=source)
    trail_summary = _inspect_records(records, proposal_id=proposal_id)

    return build_controlled_retry_guarded_repair_golden_path_report(
        trail_summary,
        proposal_id=proposal_id,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the controlled retry guarded repair golden path.",
    )
    parser.add_argument("--db-path", default=config.crdt_db_path)
    parser.add_argument("--proposal-id", default="replay-retry-real-observe-smoke-1")
    parser.add_argument("--source", default="golden-path-smoke")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Print report but exit 0 even when the golden path fails.",
    )
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    report = run_golden_path_smoke(args)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_report(report))

    if report.get("status") != "passed" and not args.no_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()