"""Trade node CRDT refresh helpers."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("SwarmNode")


def refresh_crdt_state(node: Any) -> int:
    """Best-effort refresh of CRDT in-memory state from storage.

    This allows a live trade node to see directives written by another process.
    Returns the number of refreshed records when available.
    """
    crdt = getattr(node, "crdt", None)
    if crdt is None:
        return 0

    refresh = getattr(crdt, "refresh_from_storage", None)
    if callable(refresh):
        try:
            return int(refresh() or 0)
        except Exception:
            logger.exception("[%s] CRDT refresh_from_storage failed.", getattr(node, "node_id", "unknown"))
            return 0

    genome_crdt = getattr(crdt, "crdt", None)
    if genome_crdt is not None:
        refresh_genome = getattr(genome_crdt, "refresh_from_storage", None)
        if callable(refresh_genome):
            try:
                count = int(refresh_genome() or 0)
                crdt.state = dict(getattr(genome_crdt, "state", {}) or {})
                return count
            except Exception:
                logger.exception("[%s] Genome CRDT refresh_from_storage failed.", getattr(node, "node_id", "unknown"))
                return 0

    logger.debug("[%s] CRDT refresh skipped: no supported refresh method.", getattr(node, "node_id", "unknown"))
    return 0


__all__ = ["refresh_crdt_state"]