"""Publish directive lifecycle evidence back into the runtime CRDT ledger.

Example:
    python -m src.testing.publish_directive_evidence \
      --directive-id runtime-reduce-risk-1 \
      --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter
from src.testing.directive_evidence import build_directive_runtime_evidence

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish directive runtime evidence into CRDT.")
    parser.add_argument("--directive-id", required=True, help="Directive id to validate.")
    parser.add_argument("--source", default="manual-runtime-check", help="Evidence source.")
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    return parser


async def publish_directive_evidence(args: argparse.Namespace) -> dict[str, Any]:
    """Build directive evidence from CRDT state and publish it into CRDT."""
    directive_id = str(args.directive_id or "").strip()
    if not directive_id:
        raise ValueError("directive_id must be a non-empty string")

    db_path = str(args.db_path or config.crdt_db_path)
    crdt = CRDTAdapter(
        node_id=str(args.source or "manual-runtime-check"),
        db_path=db_path,
    )

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        evidence = build_directive_runtime_evidence(
            directive_id=directive_id,
            crdt_state=state,
            source=str(args.source or "manual-runtime-check"),
        )

        await crdt.add_genome(evidence)
        return evidence

    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


async def async_main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    evidence = await publish_directive_evidence(args)

    logger.info(
        "Published directive evidence: evidence_id=%s subject=%s status=%s confidence=%s directive_id=%s db=%s",
        evidence.get("evidence_id"),
        evidence.get("subject"),
        evidence.get("status"),
        evidence.get("confidence"),
        args.directive_id,
        args.db_path or config.crdt_db_path,
    )

    for check in evidence.get("checks", []):
        logger.info(
            "Evidence check: name=%s status=%s value=%s",
            check.get("name"),
            check.get("status"),
            check.get("value"),
        )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()