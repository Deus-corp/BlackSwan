"""Backward-compatible trade execution package.

Canonical location:
    src.swarms.trade.execution
"""

from __future__ import annotations

from src.swarms.trade.execution import (
    ExecutionBackend,
    LiveExecutionBackend,
    SimExecutionBackend,
    build_backend,
)

__all__ = [
    "ExecutionBackend",
    "LiveExecutionBackend",
    "SimExecutionBackend",
    "build_backend",
]