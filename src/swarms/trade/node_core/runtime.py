"""Trade node runtime lifecycle helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger("SwarmNode")


async def run_main_loop(node: Any) -> None:
    """Run the trade node main loop."""
    async with aiohttp.ClientSession() as session:
        if node.memory_api_enabled:
            await node.memory_api.load_from_db()

        while not node.shutdown_event.is_set():
            should_continue = await node._run_one_step(session)
            if not should_continue:
                break
            await asyncio.sleep(0.5)

        logger.info("[%s] Main loop exited gracefully.", node.node_id)


async def graceful_shutdown(node: Any) -> None:
    """Gracefully stop node components."""
    shutdown = getattr(node, "_graceful_shutdown_impl", None)
    if callable(shutdown):
        await shutdown()
        return

    logger.info("[%s] Graceful shutdown requested.", getattr(node, "node_id", "unknown"))


async def shutdown_watcher(node: Any) -> None:
    """Wait for shutdown event and run graceful shutdown."""
    await node.shutdown_event.wait()
    await node._graceful_shutdown()

async def run_node_start(node: Any) -> None:
    """Start the trade node runtime."""
    await node._start_impl()

def register_signal_handlers(node: Any, loop: Any) -> None:
    """Register shutdown signal handlers for the trade node."""
    node._register_signal_handlers_impl(loop)

__all__ = [
    "graceful_shutdown",
    "register_signal_handlers",
    "run_main_loop",
    "run_node_start",
    "shutdown_watcher",
]