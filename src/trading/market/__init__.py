"""
Initializes the market module, exposing key services and selectors.

This module serves as the primary entry point for market-related functionality,
including retrieving current market snapshots and executing market selection
algorithms.
"""

from typing import Final

from .selector import select_best_market
from .snapshot import MarketSnapshotService

__all__: Final[list[str]] = [
    "MarketSnapshotService",
    "select_best_market",
]