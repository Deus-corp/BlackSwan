"""Backward-compatible trade mutation metrics import.

Canonical location:
    src.swarms.trade.domain.mutation_metrics
"""

from __future__ import annotations

from src.swarms.trade.domain.mutation_metrics import (
    get_llm_stats,
    note_llm_mutation,
    update_llm_impact,
)

__all__ = [
    "get_llm_stats",
    "note_llm_mutation",
    "update_llm_impact",
]