"""Inspect replay retry governance trail records from CRDT.

This helper is read-only. It does not publish records and does not execute retry
commands.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from typing import Any, Iterable, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

TRAIL_RECORD_TYPES = {
    "replay_lifecycle_retry_proposal",
    "replay_lifecycle_retry_approval",
    "replay_lifecycle_retry_execution_plan",
    "replay_lifecycle_retry_execution_result",
    "replay_lifecycle_retry_rendered_command",
    "replay_lifecycle_retry_execution_eligibility",
    "replay_lifecycle_retry_rendered_command_result",
    "replay_lifecycle_retry_controlled_execution_result",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect replay retry governance trail records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Optional proposal_id filter.",
    )
    parser.add_argument(
        "--approval-id",
        default="",
        help="Optional approval_id filter.",
    )
    parser.add_argument(
        "--plan-id",
        default="",
        help="Optional plan_id filter.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit with code 1 when the retry governance chain is incomplete.",
    )
    return parser


def inspect_retry_governance_trail_from_records(
    records: Iterable[Any],
    *,
    proposal_id: str = "",
    approval_id: str = "",
    plan_id: str = "",
) -> dict[str, Any]:
    """Build a read-only summary of retry governance trail records."""
    clean_proposal_id = str(proposal_id or "").strip()
    clean_approval_id = str(approval_id or "").strip()
    clean_plan_id = str(plan_id or "").strip()

    trail_records = [
        dict(item)
        for item in records or []
        if isinstance(item, Mapping)
        and item.get("type") in TRAIL_RECORD_TYPES
        and _matches_filters(
            item,
            proposal_id=clean_proposal_id,
            approval_id=clean_approval_id,
            plan_id=clean_plan_id,
        )
    ]

    by_type = Counter(str(item.get("type") or "unknown") for item in trail_records)

    proposals = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_proposal"
    ]
    approvals = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_approval"
    ]
    plans = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_execution_plan"
    ]
    rendered_commands = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_rendered_command"
    ]
    rendered_command_results = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_rendered_command_result"
    ]
    eligibilities = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_execution_eligibility"
    ]
    controlled_execution_results = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_controlled_execution_result"
    ]
    results = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_execution_result"
    ]

    approval_statuses = Counter(_clean_status(item.get("status")) for item in approvals)
    plan_statuses = Counter(_clean_status(item.get("status")) for item in plans)
    result_statuses = Counter(_clean_status(item.get("status")) for item in results)
    result_reasons = Counter(str(item.get("reason") or "unknown").strip() or "unknown" for item in results)
    decision_modes = Counter(
        str(item.get("decision_mode") or "unknown").strip() or "unknown"
        for item in approvals + plans + rendered_commands
    )
    rendered_command_statuses = Counter(
        _clean_status(item.get("status")) for item in rendered_commands
    )
    rendered_command_profiles = Counter(
        str(item.get("timeout_profile") or "unknown").strip() or "unknown"
        for item in rendered_commands
    )
    rendered_command_result_statuses = Counter(
        _clean_status(item.get("status")) for item in rendered_command_results
    )
    rendered_command_result_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in rendered_command_results
    )
    eligibility_statuses = Counter(
        _clean_status(item.get("status")) for item in eligibilities
    )
    eligibility_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in eligibilities
    )
    controlled_execution_result_statuses = Counter(
        _clean_status(item.get("status")) for item in controlled_execution_results
    )
    controlled_execution_result_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in controlled_execution_results
    )
    controlled_command_parse_valid = Counter(
        str(
            bool(
                _command_parse(item).get("valid")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_command_parse_allowlist_matched = Counter(
        str(
            bool(
                _command_parse(item).get("allowlist_matched")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_command_parse_execution_performed = Counter(
        str(
            bool(
                _command_parse(item).get("execution_performed")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_execution_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_statuses = Counter(
        str(_gate_evaluation(item).get("gate_status") or "unknown").strip()
        or "unknown"
        for item in controlled_execution_results
    )
    controlled_gate_would_execute = Counter(
        str(bool(_gate_evaluation(item).get("would_execute"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_would_execute_if_enabled = Counter(
        str(bool(_gate_evaluation(item).get("would_execute_if_enabled"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_execution_performed = Counter(
        str(bool(_gate_evaluation(item).get("execution_performed"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_reasons: Counter[str] = Counter()
    for item in controlled_execution_results:
        gate_reasons = _gate_evaluation(item).get("reasons")
        if isinstance(gate_reasons, list):
            for reason_item in gate_reasons:
                clean_reason = str(reason_item or "").strip()
                if clean_reason:
                    controlled_gate_reasons[clean_reason] += 1

    chain_ids = _build_chain_ids(
        proposals=proposals,
        approvals=approvals,
        plans=plans,
        rendered_commands=rendered_commands,
        rendered_command_results=rendered_command_results,
        eligibilities=eligibilities,
        controlled_execution_results=controlled_execution_results,
        results=results,
    )

    missing_stages = _missing_stages(
        proposals=proposals,
        approvals=approvals,
        plans=plans,
        rendered_commands=rendered_commands,
        rendered_command_results=rendered_command_results,
        eligibilities=eligibilities,
        results=results,
    )

    return {
        "type": "retry_governance_trail_summary",
        "total_records": len(trail_records),
        "filters": {
            "proposal_id": clean_proposal_id or None,
            "approval_id": clean_approval_id or None,
            "plan_id": clean_plan_id or None,
        },
        "by_type": dict(by_type),
        "counts": {
            "proposals": len(proposals),
            "approvals": len(approvals),
            "plans": len(plans),
            "rendered_commands": len(rendered_commands),
            "rendered_command_results": len(rendered_command_results),
            "eligibilities": len(eligibilities),
            "controlled_execution_results": len(controlled_execution_results),
            "results": len(results),
        },
        "approval_statuses": dict(approval_statuses),
        "plan_statuses": dict(plan_statuses),
        "rendered_command_statuses": dict(rendered_command_statuses),
        "rendered_command_profiles": dict(rendered_command_profiles),
        "rendered_command_result_statuses": dict(rendered_command_result_statuses),
        "rendered_command_result_reasons": dict(rendered_command_result_reasons),
        "eligibility_statuses": dict(eligibility_statuses),
        "eligibility_reasons": dict(eligibility_reasons),
        "controlled_execution_result_statuses": dict(
            controlled_execution_result_statuses
        ),
        "controlled_execution_result_reasons": dict(
            controlled_execution_result_reasons
        ),
        "extended_controlled_execution_observed": bool(controlled_execution_results),
        "result_statuses": dict(result_statuses),
        "result_reasons": dict(result_reasons),
        "decision_modes": dict(decision_modes),
        "chain_ids": chain_ids,
        "chain_complete": not missing_stages,
        "missing_stages": missing_stages,
        "controlled_command_parse_valid": dict(controlled_command_parse_valid),
        "controlled_command_parse_allowlist_matched": dict(
            controlled_command_parse_allowlist_matched
        ),
        "controlled_command_parse_execution_performed": dict(
            controlled_command_parse_execution_performed
        ),
        "controlled_execution_operator_authorized": dict(
            controlled_execution_operator_authorized
        ),
        "controlled_gate_statuses": dict(controlled_gate_statuses),
        "controlled_gate_would_execute": dict(controlled_gate_would_execute),
        "controlled_gate_would_execute_if_enabled": dict(
            controlled_gate_would_execute_if_enabled
        ),
        "controlled_gate_execution_performed": dict(
            controlled_gate_execution_performed
        ),
        "controlled_gate_reasons": dict(controlled_gate_reasons),
    }

def _missing_stages(
    *,
    proposals: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    plans: list[Mapping[str, Any]],
    rendered_commands: list[Mapping[str, Any]],
    rendered_command_results: list[Mapping[str, Any]],
    eligibilities: list[Mapping[str, Any]],
    results: list[Mapping[str, Any]],
) -> list[str]:
    missing: list[str] = []

    if not proposals:
        missing.append("proposal")
    if not approvals:
        missing.append("approval")
    if not plans:
        missing.append("plan")
    if not rendered_commands:
        missing.append("rendered_command")
    if not rendered_command_results:
        missing.append("rendered_command_result")
    if not eligibilities:
        missing.append("execution_eligibility")
    if not results:
        missing.append("result")

    return missing


def inspect_retry_governance_trail(args: argparse.Namespace) -> dict[str, Any]:
    """Read CRDT and summarize retry governance trail records."""
    db_path = str(args.db_path or config.crdt_db_path)

    crdt = CRDTAdapter(node_id="retry-governance-trail-reader", db_path=db_path)
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        return inspect_retry_governance_trail_from_records(
            list(state.values()),
            proposal_id=str(getattr(args, "proposal_id", "") or ""),
            approval_id=str(getattr(args, "approval_id", "") or ""),
            plan_id=str(getattr(args, "plan_id", "") or ""),
        )
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    approval_id: str,
    plan_id: str,
) -> bool:
    if proposal_id and str(record.get("proposal_id") or "").strip() != proposal_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("proposal_id") or "").strip() != proposal_id:
            return False

    if approval_id and str(record.get("approval_id") or "").strip() != approval_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("approval_id") or "").strip() != approval_id:
            return False

    if plan_id and str(record.get("plan_id") or "").strip() != plan_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("plan_id") or "").strip() != plan_id:
            return False

    return True


def _clean_status(value: Any) -> str:
    return str(value or "unknown").strip().lower() or "unknown"


def _command_parse(record: Mapping[str, Any]) -> Mapping[str, Any]:
    command_parse = record.get("command_parse")
    if isinstance(command_parse, Mapping):
        return command_parse

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        nested = payload.get("command_parse")
        if isinstance(nested, Mapping):
            return nested

    return {}


def _gate_evaluation(record: Mapping[str, Any]) -> Mapping[str, Any]:
    gate_evaluation = record.get("gate_evaluation")
    if isinstance(gate_evaluation, Mapping):
        return gate_evaluation

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        nested = payload.get("gate_evaluation")
        if isinstance(nested, Mapping):
            return nested

    return {}


def _build_chain_ids(
    *,
    proposals: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    plans: list[Mapping[str, Any]],
    rendered_commands: list[Mapping[str, Any]],
    rendered_command_results: list[Mapping[str, Any]],
    eligibilities: list[Mapping[str, Any]],
    controlled_execution_results: list[Mapping[str, Any]],
    results: list[Mapping[str, Any]],
) -> dict[str, list[str]]:
    all_records = (
        proposals
        + approvals
        + plans
        + rendered_commands
        + rendered_command_results
        + eligibilities
        + controlled_execution_results
        + results
    )

    return {
        "proposal_ids": sorted(
           {
                str(item.get("proposal_id") or "").strip()
                for item in all_records
                if str(item.get("proposal_id") or "").strip()
            }
        ),
        "approval_ids": sorted(
            {
                str(item.get("approval_id") or "").strip()
                for item in approvals
                + plans
                + rendered_commands
                + rendered_command_results
                + eligibilities
                + controlled_execution_results
                + results
               if str(item.get("approval_id") or "").strip()
            }
        ),
        "plan_ids": sorted(
           {
                str(item.get("plan_id") or "").strip()
                for item in plans
                + rendered_commands
                + rendered_command_results
                + eligibilities
                + controlled_execution_results
                + results
                if str(item.get("plan_id") or "").strip()
            }
        ),
        "rendered_command_ids": sorted(
            {
                str(item.get("rendered_command_id") or "").strip()
                for item in (
                    rendered_commands
                    + rendered_command_results
                    + eligibilities
                    + controlled_execution_results
                    + results
                )
                if str(item.get("rendered_command_id") or "").strip()
            }
        ),
        "rendered_command_result_ids": sorted(
            {
                str(item.get("rendered_command_result_id") or "").strip()
                for item in rendered_command_results
                if str(item.get("rendered_command_result_id") or "").strip()
            }
        ),
        "eligibility_ids": sorted(
            {
                str(item.get("eligibility_id") or "").strip()
                for item in eligibilities
                if str(item.get("eligibility_id") or "").strip()
            }
        ),
        "controlled_execution_result_ids": sorted(
            {
                str(item.get("controlled_execution_result_id") or "").strip()
                for item in controlled_execution_results
                if str(item.get("controlled_execution_result_id") or "").strip()
            }
        ),
        "result_ids": sorted(
            {
                str(item.get("result_id") or "").strip()
                for item in results
                if str(item.get("result_id") or "").strip()
            }
        ),
    }


def _format_summary(summary: Mapping[str, Any]) -> str:
    counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
    result_statuses = (
        summary.get("result_statuses")
        if isinstance(summary.get("result_statuses"), Mapping)
        else {}
    )
    result_reasons = (
        summary.get("result_reasons")
        if isinstance(summary.get("result_reasons"), Mapping)
        else {}
    )
    rendered_command_result_statuses = (
        summary.get("rendered_command_result_statuses")
        if isinstance(summary.get("rendered_command_result_statuses"), Mapping)
        else {}
    )
    rendered_command_result_reasons = (
        summary.get("rendered_command_result_reasons")
        if isinstance(summary.get("rendered_command_result_reasons"), Mapping)
        else {}
    )
    eligibility_statuses = (
        summary.get("eligibility_statuses")
        if isinstance(summary.get("eligibility_statuses"), Mapping)
        else {}
    )
    eligibility_reasons = (
        summary.get("eligibility_reasons")
        if isinstance(summary.get("eligibility_reasons"), Mapping)
        else {}
    )
    controlled_execution_result_statuses = (
        summary.get("controlled_execution_result_statuses")
        if isinstance(summary.get("controlled_execution_result_statuses"), Mapping)
        else {}
    )
    controlled_execution_result_reasons = (
        summary.get("controlled_execution_result_reasons")
        if isinstance(summary.get("controlled_execution_result_reasons"), Mapping)
        else {}
    )
    controlled_command_parse_valid = (
        summary.get("controlled_command_parse_valid")
        if isinstance(summary.get("controlled_command_parse_valid"), Mapping)
        else {}
    )
    controlled_command_parse_allowlist_matched = (
        summary.get("controlled_command_parse_allowlist_matched")
        if isinstance(summary.get("controlled_command_parse_allowlist_matched"), Mapping)
        else {}
    )
    controlled_command_parse_execution_performed = (
        summary.get("controlled_command_parse_execution_performed")
        if isinstance(summary.get("controlled_command_parse_execution_performed"), Mapping)
        else {}
    )
    controlled_execution_operator_authorized = (
        summary.get("controlled_execution_operator_authorized")
        if isinstance(summary.get("controlled_execution_operator_authorized"), Mapping)
        else {}
    )
    controlled_gate_statuses = (
        summary.get("controlled_gate_statuses")
        if isinstance(summary.get("controlled_gate_statuses"), Mapping)
        else {}
    )
    controlled_gate_would_execute = (
        summary.get("controlled_gate_would_execute")
        if isinstance(summary.get("controlled_gate_would_execute"), Mapping)
        else {}
    )
    controlled_gate_would_execute_if_enabled = (
        summary.get("controlled_gate_would_execute_if_enabled")
        if isinstance(summary.get("controlled_gate_would_execute_if_enabled"), Mapping)
        else {}
    )
    controlled_gate_execution_performed = (
        summary.get("controlled_gate_execution_performed")
        if isinstance(summary.get("controlled_gate_execution_performed"), Mapping)
        else {}
    )
    controlled_gate_reasons = (
        summary.get("controlled_gate_reasons")
        if isinstance(summary.get("controlled_gate_reasons"), Mapping)
        else {}
    )

    chain_complete = bool(summary.get("chain_complete"))
    missing_stages = summary.get("missing_stages")
    if isinstance(missing_stages, list):
        missing_text = ",".join(str(item) for item in missing_stages) or "none"
    else:
        missing_text = "unknown"

    return (
        "Retry governance trail: "
        f"proposals={counts.get('proposals', 0)} "
        f"approvals={counts.get('approvals', 0)} "
        f"plans={counts.get('plans', 0)} "
        f"rendered={counts.get('rendered_commands', 0)} "
        f"rendered_results={counts.get('rendered_command_results', 0)} "
        f"eligibilities={counts.get('eligibilities', 0)} "
        f"controlled_results={counts.get('controlled_execution_results', 0)} "
        f"results={counts.get('results', 0)} "
        f"skipped={result_statuses.get('skipped', 0)} "
        f"rejected={result_statuses.get('rejected', 0)} "
        f"execution_disabled={result_reasons.get('execution_disabled', 0)} "
        f"execution_not_supported={result_reasons.get('execution_not_supported', 0)} "
        f"rendered_skipped={rendered_command_result_statuses.get('skipped', 0)} "
        f"rendered_execution_disabled={rendered_command_result_reasons.get('execution_disabled', 0)} "
        f"blocked={eligibility_statuses.get('blocked', 0)} "
        f"eligibility_execution_disabled={eligibility_reasons.get('execution_disabled', 0)} "
        f"controlled_rejected={controlled_execution_result_statuses.get('rejected', 0)} "
        f"controlled_not_implemented={controlled_execution_result_reasons.get('controlled_execution_not_implemented', 0)} "
        f"extended_controlled_execution_observed={str(bool(summary.get('extended_controlled_execution_observed'))).lower()} "
        f"chain_complete={str(chain_complete).lower()} "
        f"missing_stages={missing_text} "
        f"command_parse_valid={controlled_command_parse_valid.get('true', 0)} "
        f"command_parse_allowlisted={controlled_command_parse_allowlist_matched.get('true', 0)} "
        f"command_parse_execution_performed={controlled_command_parse_execution_performed.get('true', 0)} "
        f"operator_authorized={controlled_execution_operator_authorized.get('true', 0)} "
        f"gate_blocked={controlled_gate_statuses.get('blocked', 0)} "
        f"gate_would_execute={controlled_gate_would_execute.get('true', 0)} "
        f"gate_would_execute_if_enabled={controlled_gate_would_execute_if_enabled.get('true', 0)} "
        f"gate_execution_performed={controlled_gate_execution_performed.get('true', 0)} "
        f"gate_not_enabled={controlled_gate_reasons.get('controlled_execution_not_enabled', 0)} "
    )


def _exit_code_for_summary(
    summary: Mapping[str, Any],
    *,
    require_complete: bool = False,
) -> int:
    if require_complete and not bool(summary.get("chain_complete")):
        return 1
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    summary = inspect_retry_governance_trail(args)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_format_summary(summary))

    raise SystemExit(
        _exit_code_for_summary(
            summary,
            require_complete=bool(getattr(args, "require_complete", False)),
        )
    )


if __name__ == "__main__":
    main()