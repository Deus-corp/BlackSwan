"""Canonical trade swarm execution package."""

from __future__ import annotations

from src.swarms.trade.execution.backend import ExecutionBackend
from src.swarms.trade.execution.factory import build_backend
from src.swarms.trade.execution.live_backend import LiveExecutionBackend
from src.swarms.trade.execution.sim_backend import SimExecutionBackend

__all__ = [
    "ExecutionBackend",
    "LiveExecutionBackend",
    "SimExecutionBackend",
    "build_backend",
]