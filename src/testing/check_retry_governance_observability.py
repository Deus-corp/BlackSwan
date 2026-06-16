"""Check retry governance trail observability through Security and Overseer brief.

This helper is read-only. It verifies that retry governance records are visible
to Security validation metrics and Overseer global brief key metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.overseer.overseer_core.brief_builder import build_global_swarm_brief
from src.swarms.security.runtime_validation import build_security_validation_heartbeat_metrics
from swarm_config import config

from src.testing.controlled_retry_execution_adapter import (
    describe_controlled_retry_execution_adapter_contract,
)
from src.testing.inspect_retry_governance_trail import (
    inspect_retry_governance_trail_from_records,
)

logger = logging.getLogger(__name__)

REQUIRED_RECORD_TYPES = {
    "replay_lifecycle_retry_proposal": "security_retry_proposals",
    "replay_lifecycle_retry_approval": "security_retry_approvals",
    "replay_lifecycle_retry_execution_plan": "security_retry_execution_plans",
    "replay_lifecycle_retry_execution_result": "security_retry_execution_results",
    "replay_lifecycle_retry_rendered_command": "security_retry_rendered_commands",
    "replay_lifecycle_retry_rendered_command_result": "security_retry_rendered_command_results",
    "replay_lifecycle_retry_execution_eligibility": "security_retry_execution_eligibilities",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check retry governance observability through Security and Overseer brief.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Optional proposal_id filter for the trail records.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result.",
    )
    return parser


def check_retry_governance_observability_from_records(
    records: list[Any],
    *,
    proposal_id: str = "",
) -> dict[str, Any]:
    """Check retry governance observability from CRDT records."""
    clean_proposal_id = str(proposal_id or "").strip()

    filtered_records = [
        item
        for item in records or []
        if isinstance(item, Mapping)
        and (
            not clean_proposal_id
            or str(item.get("proposal_id") or "").strip() == clean_proposal_id
            or (
                isinstance(item.get("payload"), Mapping)
                and str(item.get("payload", {}).get("proposal_id") or "").strip()
                == clean_proposal_id
            )
        )
    ]

    trail_summary = inspect_retry_governance_trail_from_records(filtered_records)
    security_metrics = build_security_validation_heartbeat_metrics(filtered_records)

    security_metrics = {
        **security_metrics,
        "real_read_only_feedback_statuses": trail_summary.get(
            "real_read_only_feedback_statuses", {}
        ),
        "real_read_only_feedback_source_statuses": trail_summary.get(
            "real_read_only_feedback_source_statuses", {}
        ),
        "real_read_only_feedback_source_exit_codes": trail_summary.get(
            "real_read_only_feedback_source_exit_codes", {}
        ),
        "real_read_only_feedback_next_actions": trail_summary.get(
            "real_read_only_feedback_next_actions", {}
        ),
        "real_read_only_feedback_real_execution_enabled": trail_summary.get(
            "real_read_only_feedback_real_execution_enabled", {}
        ),
        "real_read_only_feedback_execution_performed": trail_summary.get(
            "real_read_only_feedback_execution_performed", {}
        ),
        "real_read_only_feedback_subprocess_invoked": trail_summary.get(
            "real_read_only_feedback_subprocess_invoked", {}
        ),
        "real_read_only_feedback_feedback_execution_performed": trail_summary.get(
            "real_read_only_feedback_feedback_execution_performed", {}
        ),
        "real_read_only_feedback_feedback_subprocess_invoked": trail_summary.get(
            "real_read_only_feedback_feedback_subprocess_invoked", {}
        ),
        "real_read_only_repair_plan_statuses": trail_summary.get(
            "real_read_only_repair_plan_statuses", {}
        ),
        "real_read_only_repair_plan_source_feedback_statuses": trail_summary.get(
            "real_read_only_repair_plan_source_feedback_statuses", {}
        ),
        "real_read_only_repair_plan_source_statuses": trail_summary.get(
            "real_read_only_repair_plan_source_statuses", {}
        ),
        "real_read_only_repair_plan_source_exit_codes": trail_summary.get(
            "real_read_only_repair_plan_source_exit_codes", {}
        ),
        "real_read_only_repair_plan_next_actions": trail_summary.get(
            "real_read_only_repair_plan_next_actions", {}
        ),
        "real_read_only_repair_plan_item_counts": trail_summary.get(
            "real_read_only_repair_plan_item_counts", {}
        ),
        "real_read_only_repair_plan_requires_operator_review": trail_summary.get(
            "real_read_only_repair_plan_requires_operator_review", {}
        ),
        "real_read_only_repair_plan_repair_execution_enabled": trail_summary.get(
            "real_read_only_repair_plan_repair_execution_enabled", {}
        ),
        "real_read_only_repair_plan_real_execution_enabled": trail_summary.get(
            "real_read_only_repair_plan_real_execution_enabled", {}
        ),
        "real_read_only_repair_plan_subprocess_enabled": trail_summary.get(
            "real_read_only_repair_plan_subprocess_enabled", {}
        ),
        "real_read_only_repair_plan_repair_execution_performed": trail_summary.get(
            "real_read_only_repair_plan_repair_execution_performed", {}
        ),
        "real_read_only_repair_plan_repair_subprocess_invoked": trail_summary.get(
            "real_read_only_repair_plan_repair_subprocess_invoked", {}
        ),
        "real_read_only_repair_plan_execution_performed": trail_summary.get(
            "real_read_only_repair_plan_execution_performed", {}
        ),
        "real_read_only_repair_plan_subprocess_invoked": trail_summary.get(
            "real_read_only_repair_plan_subprocess_invoked", {}
        ),
        "real_read_only_repair_action_bundle_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_statuses", {}
        ),
        "real_read_only_repair_action_bundle_source_plan_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_source_plan_statuses", {}
        ),
        "real_read_only_repair_action_bundle_source_feedback_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_source_feedback_statuses", {}
        ),
        "real_read_only_repair_action_bundle_source_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_source_statuses", {}
        ),
        "real_read_only_repair_action_bundle_source_exit_codes": trail_summary.get(
            "real_read_only_repair_action_bundle_source_exit_codes", {}
        ),
        "real_read_only_repair_action_bundle_next_actions": trail_summary.get(
            "real_read_only_repair_action_bundle_next_actions", {}
        ),
        "real_read_only_repair_action_bundle_item_counts": trail_summary.get(
            "real_read_only_repair_action_bundle_item_counts", {}
        ),
        "real_read_only_repair_action_bundle_source_item_counts": trail_summary.get(
            "real_read_only_repair_action_bundle_source_item_counts", {}
        ),
        "real_read_only_repair_action_bundle_requires_operator_review": trail_summary.get(
            "real_read_only_repair_action_bundle_requires_operator_review", {}
        ),
        "real_read_only_repair_action_bundle_reviewed": trail_summary.get(
            "real_read_only_repair_action_bundle_reviewed", {}
        ),
        "real_read_only_repair_action_bundle_bundle_execution_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_bundle_execution_enabled", {}
        ),
        "real_read_only_repair_action_bundle_repair_execution_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_repair_execution_enabled", {}
        ),
        "real_read_only_repair_action_bundle_real_execution_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_real_execution_enabled", {}
        ),
        "real_read_only_repair_action_bundle_subprocess_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_subprocess_enabled", {}
        ),
        "real_read_only_repair_action_bundle_bundle_execution_performed": trail_summary.get(
            "real_read_only_repair_action_bundle_bundle_execution_performed", {}
        ),
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": trail_summary.get(
            "real_read_only_repair_action_bundle_bundle_subprocess_invoked", {}
        ),
        "real_read_only_repair_action_bundle_execution_performed": trail_summary.get(
            "real_read_only_repair_action_bundle_execution_performed", {}
        ),
        "real_read_only_repair_action_bundle_subprocess_invoked": trail_summary.get(
            "real_read_only_repair_action_bundle_subprocess_invoked", {}
        ),
        "real_read_only_repair_action_bundle_review_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_review_statuses", {}
        ),
        "real_read_only_repair_action_bundle_review_source_bundle_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_review_source_bundle_statuses", {}
        ),
        "real_read_only_repair_action_bundle_review_source_plan_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_review_source_plan_statuses", {}
        ),
        "real_read_only_repair_action_bundle_review_source_feedback_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_review_source_feedback_statuses", {}
        ),
        "real_read_only_repair_action_bundle_review_source_statuses": trail_summary.get(
            "real_read_only_repair_action_bundle_review_source_statuses", {}
        ),
        "real_read_only_repair_action_bundle_review_source_exit_codes": trail_summary.get(
            "real_read_only_repair_action_bundle_review_source_exit_codes", {}
        ),
        "real_read_only_repair_action_bundle_review_source_item_counts": trail_summary.get(
            "real_read_only_repair_action_bundle_review_source_item_counts", {}
        ),
        "real_read_only_repair_action_bundle_review_next_actions": trail_summary.get(
            "real_read_only_repair_action_bundle_review_next_actions", {}
        ),
        "real_read_only_repair_action_bundle_review_operator_authorized": trail_summary.get(
            "real_read_only_repair_action_bundle_review_operator_authorized", {}
        ),
        "real_read_only_repair_action_bundle_review_reviewed": trail_summary.get(
            "real_read_only_repair_action_bundle_review_reviewed", {}
        ),
        "real_read_only_repair_action_bundle_review_approved": trail_summary.get(
            "real_read_only_repair_action_bundle_review_approved", {}
        ),
        "real_read_only_repair_action_bundle_review_rejected": trail_summary.get(
            "real_read_only_repair_action_bundle_review_rejected", {}
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_review_bundle_execution_enabled", {}
        ),
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_review_repair_execution_enabled", {}
        ),
        "real_read_only_repair_action_bundle_review_real_execution_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_review_real_execution_enabled", {}
        ),
        "real_read_only_repair_action_bundle_review_subprocess_enabled": trail_summary.get(
            "real_read_only_repair_action_bundle_review_subprocess_enabled", {}
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": trail_summary.get(
            "real_read_only_repair_action_bundle_review_bundle_execution_performed", {}
        ),
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": trail_summary.get(
            "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked", {}
        ),
        "real_read_only_repair_action_bundle_review_execution_performed": trail_summary.get(
            "real_read_only_repair_action_bundle_review_execution_performed", {}
        ),
        "real_read_only_repair_action_bundle_review_subprocess_invoked": trail_summary.get(
            "real_read_only_repair_action_bundle_review_subprocess_invoked", {}
        ),
        "real_execution_sandbox_adapter_scaffold_statuses": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_statuses", {}
        ),
        "real_execution_sandbox_adapter_scaffold_fail_closed": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_fail_closed", {}
        ),
        "real_execution_sandbox_adapter_scaffold_deny_by_default": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_deny_by_default", {}
        ),
        "real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled", {}
        ),
        "real_execution_sandbox_adapter_scaffold_execution_performed": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_execution_performed", {}
        ),
        "real_execution_sandbox_adapter_scaffold_subprocess_invoked": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_subprocess_invoked", {}
        ),
        "real_execution_sandbox_adapter_scaffold_real_execution_enabled": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_real_execution_enabled", {}
        ),
        "real_execution_sandbox_adapter_scaffold_external_side_effects_performed": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_external_side_effects_performed",
            {},
        ),
        "real_execution_sandbox_adapter_scaffold_production_paths_mutated": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_production_paths_mutated", {}
        ),
        "real_execution_sandbox_adapter_scaffold_production_secrets_accessed": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_production_secrets_accessed",
            {},
        ),
        "real_execution_sandbox_adapter_scaffold_orphans": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_orphans", 0
        ),
        "real_execution_sandbox_adapter_scaffold_linkage_complete": trail_summary.get(
            "real_execution_sandbox_adapter_scaffold_linkage_complete", False
        ),
    }

    brief = build_global_swarm_brief(
        snapshot={"active_swarm_counts": {"security": 1, "overseer": 1}},
        security_validation=security_metrics,
    )

    record_type_counts = security_metrics.get("security_validation_record_type_counts")
    if not isinstance(record_type_counts, Mapping):
        record_type_counts = {}

    key_metrics = brief.key_metrics if isinstance(brief.key_metrics, Mapping) else {}

    checks = _build_checks(
        record_type_counts=record_type_counts,
        key_metrics=key_metrics,
    )

    status = "passed" if all(item["status"] == "passed" for item in checks) else "failed"

    brief_key_metrics = dict(getattr(brief, "key_metrics", {}) or {})

    unsupported_real_adapter_metrics = _unsupported_real_adapter_metrics()

    brief_key_metrics["security_real_adapter_supported"] = 0
    brief_key_metrics["security_real_adapter_runnable"] = 0
    brief_key_metrics["security_real_adapter_subprocess_supported"] = 0
    brief_key_metrics["security_real_adapter_requires_explicit_pr"] = (
        unsupported_real_adapter_metrics[
            "security_real_adapter_requires_explicit_pr"
        ]
    )

    return {
        "type": "retry_governance_observability_check",
        "status": status,
        "checks": checks,
        "proposal_id": clean_proposal_id or None,
        "security_record_type_counts": dict(record_type_counts),
        "brief_key_metrics": brief_key_metrics,
        "brief_summary": brief.summary,
    }


def check_retry_governance_observability(args: argparse.Namespace) -> dict[str, Any]:
    """Read CRDT and check retry governance observability."""
    db_path = str(args.db_path or config.crdt_db_path)

    crdt = CRDTAdapter(node_id="retry-governance-observability-reader", db_path=db_path)
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        return check_retry_governance_observability_from_records(
            list(state.values()),
            proposal_id=str(getattr(args, "proposal_id", "") or ""),
        )
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _build_checks(
    *,
    record_type_counts: Mapping[str, Any],
    key_metrics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    for record_type, metric_name in REQUIRED_RECORD_TYPES.items():
        security_count = _safe_int(record_type_counts.get(record_type), 0)
        brief_count = _safe_int(key_metrics.get(metric_name), 0)

        checks.append(
            {
                "name": f"security_observes_{record_type}",
                "status": "passed" if security_count > 0 else "failed",
                "value": security_count,
            }
        )
        checks.append(
            {
                "name": f"brief_surfaces_{metric_name}",
                "status": "passed" if brief_count > 0 else "failed",
                "value": brief_count,
            }
        )

    rendered_profiles = key_metrics.get("security_retry_rendered_command_profiles")
    if not isinstance(rendered_profiles, Mapping):
        rendered_profiles = {}

    rendered_standard = _safe_int(rendered_profiles.get("standard"), 0)
    rendered_patient = _safe_int(rendered_profiles.get("patient"), 0)

    checks.append(
        {
            "name": "brief_surfaces_retry_rendered_command_profile_breakdown",
            "status": "passed" if rendered_standard > 0 or rendered_patient > 0 else "failed",
            "value": dict(rendered_profiles),
        }
    )

    skipped = _safe_int(key_metrics.get("security_retry_execution_skipped"), 0)
    checks.append(
        {
            "name": "brief_surfaces_retry_execution_skipped",
            "status": "passed" if skipped > 0 else "failed",
            "value": skipped,
        }
    )

    rendered_result_statuses = key_metrics.get("security_retry_rendered_command_result_statuses")
    if not isinstance(rendered_result_statuses, Mapping):
        rendered_result_statuses = {}

    rendered_result_reasons = key_metrics.get("security_retry_rendered_command_result_reasons")
    if not isinstance(rendered_result_reasons, Mapping):
        rendered_result_reasons = {}

    checks.append(
        {
            "name": "brief_surfaces_retry_rendered_command_result_status_breakdown",
            "status": (
                "passed"
                if _safe_int(rendered_result_statuses.get("skipped"), 0) > 0
                or _safe_int(rendered_result_statuses.get("rejected"), 0) > 0
                else "failed"
            ),
            "value": dict(rendered_result_statuses),
        }
    )
    checks.append(
        {
            "name": "brief_surfaces_retry_rendered_command_result_reason_breakdown",
            "status": (
                "passed"
                if _safe_int(rendered_result_reasons.get("execution_disabled"), 0) > 0
                or _safe_int(rendered_result_reasons.get("execution_not_supported"), 0) > 0
                else "failed"
            ),
            "value": dict(rendered_result_reasons),
        }
    )

    result_statuses = key_metrics.get("security_retry_execution_result_statuses")
    if not isinstance(result_statuses, Mapping):
        result_statuses = {}

    result_reasons = key_metrics.get("security_retry_execution_result_reasons")
    if not isinstance(result_reasons, Mapping):
        result_reasons = {}

    checks.append(
        {
            "name": "brief_surfaces_retry_execution_result_status_breakdown",
            "status": "passed" if _safe_int(result_statuses.get("skipped"), 0) > 0 else "failed",
            "value": dict(result_statuses),
        }
    )
    checks.append(
        {
            "name": "brief_surfaces_retry_execution_result_reason_breakdown",
            "status": "passed" if _safe_int(result_reasons.get("execution_disabled"), 0) > 0 else "failed",
            "value": dict(result_reasons),
        }
    )

    eligibility_statuses = key_metrics.get("security_retry_execution_eligibility_statuses")
    if not isinstance(eligibility_statuses, Mapping):
        eligibility_statuses = {}

    eligibility_reasons = key_metrics.get("security_retry_execution_eligibility_reasons")
    if not isinstance(eligibility_reasons, Mapping):
        eligibility_reasons = {}

    checks.append(
        {
            "name": "brief_surfaces_retry_execution_eligibility_status_breakdown",
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
            "name": "brief_surfaces_retry_execution_eligibility_reason_breakdown",
            "status": (
                "passed"
                if _safe_int(eligibility_reasons.get("execution_disabled"), 0) > 0
                or _safe_int(eligibility_reasons.get("execution_not_supported"), 0) > 0
                or _safe_int(eligibility_reasons.get("missing_rendered_command_result"), 0) > 0
                or _safe_int(eligibility_reasons.get("missing_rendered_command"), 0) > 0
                else "failed"
            ),
            "value": dict(eligibility_reasons),
        }
    )

    return checks


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _unsupported_real_adapter_metrics() -> dict[str, int]:
    contract = describe_controlled_retry_execution_adapter_contract()
    real_contract = contract.get("real_adapter_contract")
    real_mapping = real_contract if isinstance(real_contract, Mapping) else {}

    return {
        "security_real_adapter_supported": int(
            bool(contract.get("real_execution_supported"))
        ),
        "security_real_adapter_runnable": int(bool(real_mapping.get("runnable"))),
        "security_real_adapter_subprocess_supported": int(
            bool(contract.get("subprocess_supported"))
        ),
        "security_real_adapter_requires_explicit_pr": int(
            bool(real_mapping.get("requires_explicit_pr"))
        ),
    }


def _format_result(result: Mapping[str, Any]) -> str:
    checks = result.get("checks")
    if not isinstance(checks, list):
        checks = []

    failed = [
        str(item.get("name") or "unknown")
        for item in checks
        if isinstance(item, Mapping) and item.get("status") != "passed"
    ]

    return (
        "Retry governance observability: "
        f"status={result.get('status')} "
        f"checks={len(checks)} "
        f"failed={len(failed)} "
        f"failed_checks={','.join(failed) if failed else 'none'}"
    )


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    result = check_retry_governance_observability(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()