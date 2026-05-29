"""Trade node one-step runtime helpers."""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger("SwarmNode")


async def maybe_trigger_failure_shutdown(node: Any) -> bool:
    """Return True if simulated failure shutdown was triggered."""
    failure_prob = float(getattr(node, "failure_prob", 0.0) or 0.0)
    if failure_prob <= 0.0:
        return False

    if random.random() >= failure_prob:
        return False

    logger.warning("[%s] Simulated failure triggered. Requesting shutdown.", node.node_id)
    node.shutdown_event.set()
    return True


def apply_capital_burn_and_check_alive(node: Any) -> bool:
    """Apply capital burn and return whether node remains alive."""
    burn_rate = float(getattr(node, "burn_rate", 0.0) or 0.0)

    capital_mgr = getattr(node, "capital_mgr", None)
    if capital_mgr is not None and hasattr(capital_mgr, "burn"):
        try:
            capital_mgr.burn(burn_rate)
        except TypeError:
            capital_mgr.burn()

    node.capital = float(getattr(capital_mgr, "capital", getattr(node, "capital", 0.0)) or 0.0)

    if capital_mgr is not None and hasattr(capital_mgr, "is_alive"):
        alive = bool(capital_mgr.is_alive())
    else:
        alive = node.capital > 0.0

    if not alive:
        logger.critical("[%s] Node capital depleted. Requesting shutdown.", node.node_id)
        node.shutdown_event.set()

    return alive


__all__ = [
    "apply_capital_burn_and_check_alive",
    "maybe_trigger_failure_shutdown",
]