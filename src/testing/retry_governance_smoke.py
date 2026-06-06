"""One-command smoke check for retry governance trail.

Seeds a synthetic non-executing retry governance trail, verifies chain
completeness, runs rendered-command dry-run, and checks Security/Overseer
observability.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from src.testing.check_retry_governance_observability import (
    _exit_code_for_result as observability_exit_code,
    check_retry_governance_observability,
)
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary as trail_exit_code,
    inspect_retry_governance_trail,
)
from src.testing.run_rendered_retry_commands import run_rendered_retry_commands
from src.testing.seed_retry_governance_trail import seed_retry_governance_trail
from swarm_config import config

logger = logging.getLogger(__name__)


RETRY_GOVERNANCE_RECORD_TYPES = {
    "replay_lifecycle_retry_proposal",
    "replay_lifecycle_retry_approval",
    "replay_lifecycle_retry_execution_plan",
    "replay_lifecycle_retry_rendered_command",
    "replay_lifecycle_retry_rendered_command_result",
    "replay_lifecycle_retry_execution_result",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run retry governance smoke check.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="retry-governance-smoke",
        help="Source node id for seeded records.",
    )
    parser.add_argument(
        "--proposal-id",
        default="replay-retry-smoke-proposal-1",
        help="Synthetic proposal id.",
    )
    parser.add_argument(
        "--approval-id",
        default="replay-retry-smoke-approval-1",
        help="Synthetic approval id.",
    )
    parser.add_argument(
        "--plan-id",
        default="replay-retry-smoke-plan-1",
        help="Synthetic plan id.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="replay-retry-smoke-rendered-command-1",
        help="Synthetic rendered command id.",
    )
    parser.add_argument(
        "--result-id",
        default="replay-retry-smoke-result-1",
        help="Synthetic result id.",
    )
    parser.add_argument(
        "--timeout-profile",
        default="standard",
        choices=["standard", "patient"],
        help="Safe timeout profile.",
    )
    parser.add_argument(
        "--decision-mode",
        default="manual",
        choices=["manual", "policy"],
        help="Approval decision mode.",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail before seeding if retry governance records already exist for the proposal id.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result.",
    )
    return parser


def _existing_retry_governance_records(
    *,
    db_path: str,
    proposal_id: str,
) -> list[dict[str, Any]]:
    crdt = CRDTAdapter(node_id="retry-governance-smoke-preflight", db_path=db_path)
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        records: list[dict[str, Any]] = []

        for item in state.values():
            if not isinstance(item, Mapping):
                continue
            if item.get("type") not in RETRY_GOVERNANCE_RECORD_TYPES:
                continue
            if _record_matches_proposal_id(item, proposal_id):
                records.append(dict(item))

        return records
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _record_matches_proposal_id(record: Mapping[str, Any], proposal_id: str) -> bool:
    if str(record.get("proposal_id") or "").strip() == proposal_id:
        return True

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        return str(payload.get("proposal_id") or "").strip() == proposal_id

    return False


async def run_retry_governance_smoke(args: argparse.Namespace) -> dict[str, Any]:
    """Seed, dry-run, and verify retry governance trail and observability."""
    db_path = str(args.db_path or config.crdt_db_path)
    proposal_id = str(args.proposal_id or "replay-retry-smoke-proposal-1").strip()
    rendered_command_id = str(
        getattr(args, "rendered_command_id", "") or "replay-retry-smoke-rendered-command-1"
    ).strip()
    require_clean = bool(getattr(args, "require_clean", False))

    existing_records: list[dict[str, Any]] = []
    if require_clean:
        existing_records = _existing_retry_governance_records(
            db_path=db_path,
            proposal_id=proposal_id,
        )
        if existing_records:
            return {
                "type": "retry_governance_smoke_result",
                "status": "failed",
                "records_seeded": 0,
                "rendered_command_results": 0,
                "proposal_id": proposal_id,
                "reason": "existing_retry_governance_records",
                "existing_records": len(existing_records),
                "trail_summary": {},
                "observability": {},
                "exit_codes": {
                    "preflight": 1,
                    "rendered_command_results": 1,
                    "trail": 1,
                    "observability": 1,
                },
            }

    records = await seed_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            source=str(args.source or "retry-governance-smoke"),
            proposal_id=proposal_id,
            approval_id=str(args.approval_id or "replay-retry-smoke-approval-1"),
            plan_id=str(args.plan_id or "replay-retry-smoke-plan-1"),
            rendered_command_id=rendered_command_id,
            result_id=str(args.result_id or "replay-retry-smoke-result-1"),
            timeout_profile=str(args.timeout_profile or "standard"),
            decision_mode=str(args.decision_mode or "manual"),
        )
    )

    rendered_command_results = await run_rendered_retry_commands(
        argparse.Namespace(
            db_path=db_path,
            source="rendered-retry-command-smoke",
            rendered_command_id=rendered_command_id,
            plan_id="",
        )
    )

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

    trail_code = trail_exit_code(trail_summary, require_complete=True)
    observability_code = observability_exit_code(observability)
    rendered_command_result_count = len(rendered_command_results)

    status = (
        "passed"
        if trail_code == 0
        and observability_code == 0
        and rendered_command_result_count > 0
        else "failed"
    )

    return {
        "type": "retry_governance_smoke_result",
        "status": status,
        "records_seeded": len(records),
        "rendered_command_results": rendered_command_result_count,
        "proposal_id": proposal_id,
        "reason": "ok" if status == "passed" else "retry_governance_smoke_failed",
        "existing_records": len(existing_records),
        "trail_summary": trail_summary,
        "observability": observability,
        "exit_codes": {
            "preflight": 0,
            "rendered_command_results": 0 if rendered_command_result_count > 0 else 1,
            "trail": trail_code,
            "observability": observability_code,
        },
    }


def _format_result(result: Mapping[str, Any]) -> str:
    trail = result.get("trail_summary") if isinstance(result.get("trail_summary"), Mapping) else {}
    observability = result.get("observability") if isinstance(result.get("observability"), Mapping) else {}
    counts = trail.get("counts") if isinstance(trail.get("counts"), Mapping) else {}

    return (
        "Retry governance smoke: "
        f"status={result.get('status')} "
        f"records_seeded={result.get('records_seeded')} "
        f"rendered_command_results={result.get('rendered_command_results', 0)} "
        f"proposals={counts.get('proposals', 0)} "
        f"approvals={counts.get('approvals', 0)} "
        f"plans={counts.get('plans', 0)} "
        f"rendered={counts.get('rendered_commands', 0)} "
        f"results={counts.get('results', 0)} "
        f"chain_complete={str(bool(trail.get('chain_complete'))).lower()} "
        f"observability={observability.get('status')} "
        f"existing_records={result.get('existing_records', 0)} "
        f"reason={result.get('reason') or 'ok'} "
    )


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    result = await run_retry_governance_smoke(args)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    return _exit_code_for_result(result)


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()