"""
Initializes the market module, exposing key services and selectors.
This module provides functionality for fetching market snapshots and
selecting the best trading market based on certain criteria.
"""
from .snapshot import MarketSnapshotService
from .selector import select_best_market

__all__ = ["MarketSnapshotService", "select_best_market"]
