"""Trade node periodic cycle helpers."""

from __future__ import annotations

from typing import Any


async def apply_meta_commands(node: Any) -> None:
    """Apply meta commands to the trade node."""
    await node._apply_meta_commands_impl()


async def evolution_cycle(node: Any) -> None:
    """Run one trade evolution cycle."""
    await node._evolution_cycle_impl()


async def sync_cycle(node: Any) -> None:
    """Run one trade swarm sync cycle."""
    await node._sync_cycle_impl()


__all__ = [
    "apply_meta_commands",
    "evolution_cycle",
    "sync_cycle",
]