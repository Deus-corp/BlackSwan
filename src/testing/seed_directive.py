"""Seed a safe cross-swarm directive into the runtime CRDT ledger.

Used for controlled runtime checks:
    python -m src.testing.seed_directive --action REDUCE_RISK --target trade
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.common.protocols.directives import (
    DirectiveSeverity,
    DirectiveTargetType,
    build_directive,
)

logger = logging.getLogger(__name__)


SAFE_SEED_ACTIONS = {
    "OBSERVE",
    "REDUCE_RISK",
    "SET_DRY_RUN",
    "PROMOTE_GOLD_CANDIDATES",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed a safe swarm directive into CRDT.")
    parser.add_argument("--action", default="REDUCE_RISK", help="Directive action.")
    parser.add_argument("--target", default="trade", help="Directive target.")
    parser.add_argument(
        "--target-type",
        default=DirectiveTargetType.SWARM.value,
        choices=[item.value for item in DirectiveTargetType],
        help="Directive target type.",
    )
    parser.add_argument("--source", default="manual-seed", help="Directive source.")
    parser.add_argument("--ttl-ms", type=int, default=300_000, help="Directive TTL in milliseconds.")
    parser.add_argument("--directive-id", default="", help="Optional deterministic directive id.")
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    return parser


async def seed_directive(args: argparse.Namespace) -> dict[str, Any]:
    action = str(args.action or "").strip().upper()
    if action not in SAFE_SEED_ACTIONS:
        raise ValueError(f"Unsafe seed action: {action}. Allowed: {sorted(SAFE_SEED_ACTIONS)}")

    payload: dict[str, Any] = {
        "seeded": True,
        "runtime_check": True,
    }

    if action in {"REDUCE_RISK", "SET_DRY_RUN"}:
        payload.update(
            {
                "dry_run": True,
                "execution_enabled": False,
            }
        )

    directive = build_directive(
        directive_id=str(args.directive_id or "") or None,
        action=action,
        source=str(args.source or "manual-seed"),
        target_type=str(args.target_type),
        target=str(args.target),
        payload=payload,
        reason="Controlled runtime directive seed.",
        severity=DirectiveSeverity.WARNING.value if action == "REDUCE_RISK" else DirectiveSeverity.INFO.value,
        ttl_ms=int(args.ttl_ms),
    )

    crdt = CRDTAdapter(
        node_id=str(args.source or "manual-seed"),
        db_path=str(args.db_path or config.crdt_db_path),
    )

    try:
        await crdt.add_genome(directive.to_dict())
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result

    return directive.to_dict()


async def async_main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    directive = await seed_directive(args)
    logger.info(
        "Seeded directive: id=%s action=%s target=%s:%s db=%s",
        directive["directive_id"],
        directive["action"],
        directive["target_type"],
        directive["target"],
        args.db_path or config.crdt_db_path,
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()