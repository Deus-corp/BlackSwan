"""Trade node configuration/context helpers."""

from __future__ import annotations

from typing import Any

from src.swarms.trade.context import RuntimeContext, TradeNodeConfig


def build_trade_config(node: Any) -> TradeNodeConfig:
    """Build trade node configuration."""
    return node._build_trade_config_impl()


def build_runtime_context(node: Any) -> RuntimeContext:
    """Build trade node runtime context."""
    return node._build_runtime_context_impl()


def sync_context(node: Any) -> None:
    """Push mutable node state into runtime context."""
    node._sync_context_impl()


def pull_context(node: Any) -> None:
    """Pull mutable runtime context state back into node fields."""
    node._pull_context_impl()


__all__ = [
    "build_runtime_context",
    "build_trade_config",
    "pull_context",
    "sync_context",
]