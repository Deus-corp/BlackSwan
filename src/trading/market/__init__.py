"""
Initializes the market module, exposing key services and selectors.
This module provides functionality for fetching market snapshots and
selecting the best trading market based on certain criteria.
"""
from typing import Final
from .snapshot import MarketSnapshotService
from .selector import select_best_market

__all__: Final = ["MarketSnapshotService", "select_best_market"]