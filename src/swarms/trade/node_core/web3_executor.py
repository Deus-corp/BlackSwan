"""Trade node Web3 executor initialization helpers."""

from __future__ import annotations

from typing import Any


async def initialize_web3_executor(node: Any) -> None:
    """Initialize Web3 execution adapter for a trade node."""
    await node._initialize_web3_executor_impl()


__all__ = ["initialize_web3_executor"]