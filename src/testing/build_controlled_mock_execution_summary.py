"""Build derived summaries for controlled mock execution outcomes.

This helper reads controlled execution result records and publishes derived
mock execution summary records. It never invokes subprocesses.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from hashlib import sha256
from typing import Any, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

CONTROLLED_RESULT_TYPE = "replay_lifecycle_retry_controlled_execution_result"
MOCK_SUMMARY_TYPE = "replay_lifecycle_retry_mock_execution_summary"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _stable_suffix(*parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _mock_execution(record: Mapping[str, Any]) -> Mapping[str, Any]:
    mock_execution = record.get("mock_execution")
    if isinstance(mock_execution, Mapping):
        return mock_execution

    payload = _payload(record)
    nested = payload.get("mock_execution")
    return nested if isinstance(nested, Mapping) else {}


def _mock_execution_payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    mock_execution = _mock_execution(record)
    nested = mock_execution.get("mock_execution")
    return nested if isinstance(nested, Mapping) else {}


def _record_matches(
    record: Mapping[str, Any],
    *,
    controlled_execution_result_id: str,
    rendered_command_id: str,
    proposal_id: str,
) -> bool:
    payload = _payload(record)

    if controlled_execution_result_id:
        if (
            _clean(record.get("controlled_execution_result_id"))
            != controlled_execution_result_id
            and _clean(payload.get("controlled_execution_result_id"))
            != controlled_execution_result_id
        ):
            return False

    if rendered_command_id:
        if (
            _clean(record.get("rendered_command_id")) != rendered_command_id
            and _clean(payload.get("rendered_command_id")) != rendered_command_id
        ):
            return False

    if proposal_id:
        if (
            _clean(record.get("proposal_id")) != proposal_id
            and _clean(payload.get("proposal_id")) != proposal_id
        ):
            return False

    return True


def _find_existing_summary(
    records: list[Mapping[str, Any]],
    *,
    controlled_execution_result_id: str,
) -> Mapping[str, Any] | None:
    for record in records:
        if record.get("type") != MOCK_SUMMARY_TYPE:
            continue
        if (
            _clean(record.get("controlled_execution_result_id"))
            == controlled_execution_result_id
            or _clean(record.get("source_controlled_execution_result_id"))
            == controlled_execution_result_id
            or _clean(_payload(record).get("controlled_execution_result_id"))
            == controlled_execution_result_id
        ):
            return record
    return None


def build_controlled_mock_execution_summary(
    controlled_result: Mapping[str, Any],
    *,
    source: str = "controlled-mock-execution-summary",
) -> dict[str, Any]:
    """Build a derived mock execution summary for one controlled result."""
    controlled_execution_result_id = _clean(
        controlled_result.get("controlled_execution_result_id")
    )
    if not controlled_execution_result_id:
        raise ValueError("controlled_execution_result_id must be present")

    rendered_command_id = _clean(controlled_result.get("rendered_command_id"))
    proposal_id = _clean(controlled_result.get("proposal_id"))
    plan_id = _clean(controlled_result.get("plan_id"))
    approval_id = _clean(controlled_result.get("approval_id"))

    mock_execution = _mock_execution(controlled_result)
    mock_payload = _mock_execution_payload(controlled_result)

    mock_status = _clean(mock_execution.get("status")) or "none"
    mock_reason = _clean(mock_execution.get("reason")) or "none"
    mock_performed = bool(mock_payload.get("performed"))
    subprocess_invoked = bool(mock_payload.get("subprocess_invoked"))
    real_execution_enabled = bool(mock_execution.get("real_execution_enabled"))
    mock_execution_enabled = bool(mock_execution.get("mock_execution_enabled"))

    payload = _payload(controlled_result)
    payload_executed = bool(payload.get("executed"))

    summary_id = (
        "replay-retry-mock-summary-"
        + _stable_suffix(controlled_execution_result_id, rendered_command_id)
    )

    status = "mock_executed" if mock_performed and not subprocess_invoked else "blocked"
    reason = (
        "mock_execution_completed"
        if mock_performed and not subprocess_invoked
        else "mock_execution_not_observed"
    )

    return {
        "type": MOCK_SUMMARY_TYPE,
        "mock_execution_summary_id": summary_id,
        "controlled_execution_result_id": controlled_execution_result_id,
        "source_controlled_execution_result_id": controlled_execution_result_id,
        "rendered_command_id": rendered_command_id,
        "proposal_id": proposal_id,
        "plan_id": plan_id,
        "approval_id": approval_id,
        "status": status,
        "reason": reason,
        "source": source,
        "mock_status": mock_status,
        "mock_reason": mock_reason,
        "mock_performed": mock_performed,
        "subprocess_invoked": subprocess_invoked,
        "real_execution_enabled": real_execution_enabled,
        "mock_execution_enabled": mock_execution_enabled,
        "payload_executed": payload_executed,
        "derived": True,
        "payload": {
            "mock_execution_summary_id": summary_id,
            "controlled_execution_result_id": controlled_execution_result_id,
            "source_controlled_execution_result_id": controlled_execution_result_id,
            "rendered_command_id": rendered_command_id,
            "proposal_id": proposal_id,
            "plan_id": plan_id,
            "approval_id": approval_id,
            "status": status,
            "reason": reason,
            "mock_status": mock_status,
            "mock_reason": mock_reason,
            "mock_performed": mock_performed,
            "subprocess_invoked": subprocess_invoked,
            "real_execution_enabled": real_execution_enabled,
            "mock_execution_enabled": mock_execution_enabled,
            "payload_executed": payload_executed,
            "executed": False,
            "derived": True,
        },
    }


async def build_controlled_mock_execution_summaries(
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Publish idempotent derived mock execution summaries."""
    db_path = str(args.db_path or config.crdt_db_path)
    source = str(getattr(args, "source", "") or "controlled-mock-execution-summary")
    controlled_execution_result_id = _clean(
        getattr(args, "controlled_execution_result_id", "")
    )
    rendered_command_id = _clean(getattr(args, "rendered_command_id", ""))
    proposal_id = _clean(getattr(args, "proposal_id", ""))

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        records = [item for item in state.values() if isinstance(item, Mapping)]

        controlled_results = [
            item
            for item in records
            if item.get("type") == CONTROLLED_RESULT_TYPE
            and _record_matches(
                item,
                controlled_execution_result_id=controlled_execution_result_id,
                rendered_command_id=rendered_command_id,
                proposal_id=proposal_id,
            )
        ]

        results: list[dict[str, Any]] = []
        for controlled_result in controlled_results:
            current_id = _clean(controlled_result.get("controlled_execution_result_id"))
            if not current_id:
                continue

            existing = _find_existing_summary(
                records,
                controlled_execution_result_id=current_id,
            )
            if existing is not None:
                logger.info(
                    "Skipping duplicate controlled mock execution summary: controlled_execution_result_id=%s",
                    current_id,
                )
                continue

            summary = build_controlled_mock_execution_summary(
                controlled_result,
                source=source,
            )
            await crdt.add_genome(summary)
            records.append(summary)
            results.append(summary)

            logger.info(
                "Published controlled mock execution summary: controlled_execution_result_id=%s status=%s reason=%s",
                current_id,
                summary.get("status"),
                summary.get("reason"),
            )

        logger.info(
            "Controlled mock execution summary builder completed: summaries=%d",
            len(results),
        )
        return results
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish derived controlled mock execution summary records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--source",
        default="controlled-mock-execution-summary",
        help="Source node id for published records.",
    )
    parser.add_argument(
        "--controlled-execution-result-id",
        default="",
        help="Optional controlled execution result id filter.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Optional rendered command id filter.",
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


async def async_main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    results = await build_controlled_mock_execution_summaries(args)

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(
            "Controlled mock execution summary builder completed: "
            f"summaries={len(results)}"
        )

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()