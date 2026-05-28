"""Backward-compatible trade market package.

Canonical location:
    src.swarms.trade.market
"""

from __future__ import annotations

from src.swarms.trade.market import (
    MarketCollector,
    MarketSnapshot,
    MarketSnapshotService,
    select_best_market,
)

__all__ = [
    "MarketCollector",
    "MarketSnapshot",
    "MarketSnapshotService",
    "select_best_market",
]