"""Seed a synthetic replay retry governance trail into CRDT.

This helper publishes safe, non-executing governance records:
proposal -> approval -> execution plan -> skipped execution result.
It does not execute retry commands.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

from src.swarms.overseer.overseer_core.replay_retry_command_rendering import (
    build_replay_lifecycle_retry_rendered_command,
)

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed a synthetic replay retry governance trail.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="retry-governance-seed",
        help="Source node id for seeded records.",
    )
    parser.add_argument(
        "--proposal-id",
        default="replay-retry-seed-proposal-1",
        help="Proposal id to seed.",
    )
    parser.add_argument(
        "--approval-id",
        default="replay-retry-seed-approval-1",
        help="Approval id to seed.",
    )
    parser.add_argument(
        "--plan-id",
        default="replay-retry-seed-plan-1",
        help="Execution plan id to seed.",
    )
    parser.add_argument(
        "--result-id",
        default="replay-retry-seed-result-1",
        help="Execution result id to seed.",
    )
    parser.add_argument(
        "--timeout-profile",
        default="standard",
        choices=["standard", "patient"],
        help="Safe retry timeout profile.",
    )
    parser.add_argument(
        "--decision-mode",
        default="manual",
        choices=["manual", "policy"],
        help="Approval decision mode.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="replay-retry-seed-rendered-command-1",
        help="Rendered command id to seed.",
    )
    return parser


async def seed_retry_governance_trail(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Publish a synthetic safe replay retry governance trail."""
    rendered_command_id = str(
        getattr(args, "rendered_command_id", "") or "replay-retry-seed-rendered-command-1"
    ).strip()
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "retry-governance-seed")

    proposal_id = str(args.proposal_id or "replay-retry-seed-proposal-1").strip()
    approval_id = str(args.approval_id or "replay-retry-seed-approval-1").strip()
    plan_id = str(args.plan_id or "replay-retry-seed-plan-1").strip()
    result_id = str(args.result_id or "replay-retry-seed-result-1").strip()
    timeout_profile = str(args.timeout_profile or "standard").strip()
    decision_mode = str(args.decision_mode or "manual").strip()

    if not proposal_id:
        raise ValueError("proposal_id must be present")
    if not approval_id:
        raise ValueError("approval_id must be present")
    if not plan_id:
        raise ValueError("plan_id must be present")
    if not result_id:
        raise ValueError("result_id must be present")
    if not rendered_command_id:
        raise ValueError("rendered_command_id must be present")
    if timeout_profile not in {"standard", "patient"}:
        raise ValueError("timeout_profile must be standard or patient")
    if decision_mode not in {"manual", "policy"}:
        raise ValueError("decision_mode must be manual or policy")

    command_template = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id <scenario_id> "
        "--action REDUCE_RISK "
        "--directive-id <new_directive_id> "
        f"--timeout-profile {timeout_profile} "
        "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
    )

    proposal = {
        "type": "replay_lifecycle_retry_proposal",
        "proposal_id": proposal_id,
        "status": "pending",
        "source": source,
        "recommendation": "retry_replay_lifecycle_check",
        "reason": "execution_not_observed_before_timeout",
        "timeout_profile": timeout_profile,
        "command_template": command_template,
        "payload": {
            "recommendation": "retry_replay_lifecycle_check",
            "reason": "execution_not_observed_before_timeout",
            "timeout_profile": timeout_profile,
            "suggested_wait_seconds": 15.0 if timeout_profile == "standard" else 60.0,
            "suggested_poll_interval": 0.5 if timeout_profile == "standard" else 1.0,
        },
    }

    approval = {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": approval_id,
        "proposal_id": proposal_id,
        "status": "approved",
        "approved_by": source,
        "source": source,
        "reason": "synthetic_governance_smoke",
        "execution_enabled": False,
        "decision_mode": decision_mode,
        "payload": {
            "proposal_id": proposal_id,
            "proposal_type": proposal["type"],
            "proposal_status": proposal["status"],
            "proposal_reason": proposal["reason"],
            "timeout_profile": timeout_profile,
            "command_template": command_template,
            "approval_status": "approved",
            "approved_by": source,
            "reason": "synthetic_governance_smoke",
            "execution_enabled": False,
            "decision_mode": decision_mode,
        },
    }

    plan = {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "status": "planned",
        "source": source,
        "execution_enabled": False,
        "timeout_profile": timeout_profile,
        "command_template": command_template,
        "decision_mode": decision_mode,
        "payload": {
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "proposal_reason": proposal["reason"],
            "approval_reason": approval["reason"],
            "timeout_profile": timeout_profile,
            "command_template": command_template,
            "decision_mode": decision_mode,
            "execution_enabled": False,
        },
    }

    rendered_command = build_replay_lifecycle_retry_rendered_command(
        plan,
        scenario_id=f"{proposal_id}-scenario",
        new_directive_id=f"{proposal_id}-directive",
        source=source,
    )
    rendered_command["rendered_command_id"] = rendered_command_id
    rendered_command["payload"]["rendered_command_id"] = rendered_command_id

    result = {
        "type": "replay_lifecycle_retry_execution_result",
        "result_id": result_id,
        "plan_id": plan_id,
        "proposal_id": proposal_id,
        "approval_id": approval_id,
        "rendered_command_id": rendered_command_id,
        "status": "skipped",
        "reason": "execution_disabled",
        "source": source,
        "execution_enabled": False,
        "payload": {
            "plan_id": plan_id,
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "rendered_command_id": rendered_command_id,
            "timeout_profile": timeout_profile,
            "decision_mode": decision_mode,
            "command_template": command_template,
            "execution_enabled": False,
            "executed": False,
        },
    }

    records = [proposal, approval, plan, rendered_command, result]

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        existing_records = [
            item for item in state.values()
            if isinstance(item, Mapping)
        ]

        published: list[dict[str, Any]] = []
        for record in records:
            existing = _find_existing_record(existing_records, record)
            if existing is not None:
                logger.info(
                    "Skipping duplicate retry governance record: type=%s id=%s",
                    record.get("type"),
                    _record_id(record),
                )
                continue

            await crdt.add_genome(record)
            existing_records.append(record)
            published.append(record)
            logger.info(
                "Seeded retry governance record: type=%s id=%s",
                record.get("type"),
                _record_id(record),
            )

        logger.info("Seeded retry governance trail: records=%d", len(published))
        return published
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _record_id(record: dict[str, Any]) -> str:
    record_type = str(record.get("type") or "").strip()

    preferred_keys_by_type = {
        "replay_lifecycle_retry_proposal": ("proposal_id",),
        "replay_lifecycle_retry_approval": ("approval_id", "proposal_id"),
        "replay_lifecycle_retry_execution_plan": ("plan_id", "approval_id", "proposal_id"),
        "replay_lifecycle_retry_execution_result": ("result_id", "plan_id", "approval_id", "proposal_id"),
        "replay_lifecycle_retry_rendered_command": ("rendered_command_id", "plan_id", "approval_id", "proposal_id"),
    }

    keys = preferred_keys_by_type.get(
        record_type,
        ("rendered_command_id", "result_id", "plan_id", "approval_id", "proposal_id")
    )

    for key in keys:
        value = str(record.get(key) or "").strip()
        if value:
            return value

    return ""


def _find_existing_record(
    records: list[Mapping[str, Any]],
    record: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    expected_type = str(record.get("type") or "").strip()
    expected_id = _record_id(record)

    if not expected_type or not expected_id:
        return None

    for item in records:
        if str(item.get("type") or "").strip() != expected_type:
            continue
        if _record_id(item) == expected_id:
            return item

    return None


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    records = await seed_retry_governance_trail(args)

    logger.info("Seeded retry governance trail: records=%d", len(records))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()