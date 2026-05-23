#!/usr/bin/env python3
"""Common swarm utility helpers.

This module intentionally provides both:
- canonical utility names used by the new common runtime
- compatibility aliases used by earlier swarm refactor passes
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .ids import (
    new_gid,
    new_meta_agent_id,
    new_node_id,
    new_overseer_id,
    new_short_id,
)
from .serialization import (
    compact_repr,
    json_dumps,
    json_loads_dict,
    json_loads_safe,
    summarize_value,
    to_jsonable,
)
from .time import (
    age_seconds,
    expires_in,
    is_expired,
    monotonic_ts,
    utc_ts,
    utc_ts_int,
)


def now_ts() -> float:
    """Compatibility alias for current UTC unix timestamp in seconds."""
    return float(utc_ts())


def now_ms() -> int:
    """Current UTC unix timestamp in milliseconds."""
    return int(float(utc_ts()) * 1000)


def utc_iso() -> str:
    """Current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "age_seconds",
    "compact_repr",
    "expires_in",
    "is_expired",
    "json_dumps",
    "json_loads_dict",
    "json_loads_safe",
    "monotonic_ts",
    "new_gid",
    "new_meta_agent_id",
    "new_node_id",
    "new_overseer_id",
    "new_short_id",
    "now_ms",
    "now_ts",
    "summarize_value",
    "to_jsonable",
    "utc_iso",
    "utc_ts",
    "utc_ts_int",
]