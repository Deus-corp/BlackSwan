"""Factory for creating ExecutionBackend instances based on configured market mode."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from .backend import ExecutionBackend
from .live_backend import LiveExecutionBackend
from .sim_backend import SimExecutionBackend

logger = logging.getLogger(__name__)

LeadershipFunc = Callable[[int], bool]
LIVE_MODES = {"web3", "live", "futures"}


def _load_config() -> Any:
    """Load swarm_config.config, adding project root to sys.path if needed."""
    try:
        from swarm_config import config

        return config
    except ImportError:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "../../.."))

        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        try:
            from swarm_config import config

            return config
        except ImportError as exc:
            raise ImportError(
                "Could not import 'config' from 'swarm_config'. "
                "Ensure swarm_config.py is available from the project root or PYTHONPATH."
            ) from exc


config = _load_config()


def build_backend(
    node_id: str,
    adapter: Any,
    is_leader_func: LeadershipFunc,
    *,
    market_mode: str | None = None,
    allow_sim_fallback: bool = True,
) -> ExecutionBackend:
    """Build an execution backend for sim, web3, live, or futures modes.

    In live-like modes, SwarmNode may call this before the Web3 adapter is initialized.
    When adapter is missing and allow_sim_fallback=True, this returns SimExecutionBackend
    instead of failing during construction. Runtime code may rebuild the backend after
    adapter initialization.
    """
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id:
        raise ValueError("node_id cannot be empty")

    if not callable(is_leader_func):
        raise TypeError("is_leader_func must be callable")

    mode = _resolve_market_mode(market_mode)

    if mode == "sim":
        return SimExecutionBackend()

    if mode in LIVE_MODES:
        if adapter is None:
            if allow_sim_fallback:
                logger.warning(
                    "[%s] Adapter is not initialized for market_mode=%r; "
                    "using SimExecutionBackend fallback until live adapter is available.",
                    clean_node_id,
                    mode,
                )
                return SimExecutionBackend()

            raise ValueError(f"adapter is required for market_mode={mode!r}")

        return LiveExecutionBackend(clean_node_id, adapter, is_leader_func)

    raise ValueError(f"Unsupported market mode: {mode!r}")


def _resolve_market_mode(override: str | None = None) -> str:
    raw_mode = (
        override
        or os.environ.get("MARKET_MODE")
        or os.environ.get("TRADING_MARKET_MODE")
        or getattr(config, "market_mode", None)
        or getattr(getattr(config, "trading", None), "market_mode", None)
        or "sim"
    )
    return str(raw_mode).strip().lower()