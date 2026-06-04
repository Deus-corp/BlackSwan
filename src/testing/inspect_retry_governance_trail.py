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

    chain_ids = _build_chain_ids(
        proposals=proposals,
        approvals=approvals,
        plans=plans,
        rendered_commands=rendered_commands,
        results=results,
    )

    missing_stages = _missing_stages(
        proposals=proposals,
        approvals=approvals,
        plans=plans,
        rendered_commands=rendered_commands,
        results=results,
    )

    return {
        "type": "retry_governance_trail_summary",
        "total_records": len(trail_records),
        "counts": {
            "proposals": len(proposals),
            "approvals": len(approvals),
            "plans": len(plans),
            "rendered_commands": len(rendered_commands),
            "results": len(results),
        },
        "by_type": dict(by_type),
        "approval_statuses": dict(approval_statuses),
        "plan_statuses": dict(plan_statuses),
        "result_statuses": dict(result_statuses),
        "result_reasons": dict(result_reasons),
        "decision_modes": dict(decision_modes),
        "chain_ids": chain_ids,
        "filters": {
            "proposal_id": clean_proposal_id or None,
            "approval_id": clean_approval_id or None,
            "plan_id": clean_plan_id or None,
        },
        "chain_complete": not missing_stages,
        "missing_stages": missing_stages,
        "rendered_command_statuses": dict(rendered_command_statuses),
        "rendered_command_profiles": dict(rendered_command_profiles),
    }

def _missing_stages(
    *,
    proposals: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    plans: list[Mapping[str, Any]],
    rendered_commands: list[Mapping[str, Any]],
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


def _build_chain_ids(
    *,
    proposals: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    plans: list[Mapping[str, Any]],
    rendered_commands: list[Mapping[str, Any]],
    results: list[Mapping[str, Any]],
) -> dict[str, list[str]]:
    all_records = proposals + approvals + plans + rendered_commands + results

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
                for item in approvals + plans + rendered_commands + results
                if str(item.get("approval_id") or "").strip()
            }
        ),
        "plan_ids": sorted(
            {
                str(item.get("plan_id") or "").strip()
                for item in plans + rendered_commands + results
                if str(item.get("plan_id") or "").strip()
            }
        ),
        "rendered_command_ids": sorted(
            {
                str(item.get("rendered_command_id") or "").strip()
                for item in rendered_commands + results
                if str(item.get("rendered_command_id") or "").strip()
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
        f"results={counts.get('results', 0)} "
        f"skipped={result_statuses.get('skipped', 0)} "
        f"rejected={result_statuses.get('rejected', 0)} "
        f"execution_disabled={result_reasons.get('execution_disabled', 0)} "
        f"execution_not_supported={result_reasons.get('execution_not_supported', 0)} "
        f"chain_complete={str(chain_complete).lower()} "
        f"missing_stages={missing_text} "
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