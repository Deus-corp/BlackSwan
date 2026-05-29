"""Trade node command loop helper."""

from __future__ import annotations

from typing import Any


async def run_command_loop(node: Any) -> None:
    """Run trade node command loop."""
    await node._command_loop_impl()


__all__ = ["run_command_loop"]