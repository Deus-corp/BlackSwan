"""Trade node leadership helpers."""

from __future__ import annotations

from typing import Any


def is_leader(node: Any, block_number: int) -> bool:
    """Return True if this node is leader for a given block number."""
    return node._is_leader_impl(block_number)


__all__ = ["is_leader"]