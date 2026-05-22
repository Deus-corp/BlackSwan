#!/usr/bin/env python3
"""Time utilities for swarm runtime."""

from __future__ import annotations

import time


def utc_ts() -> float:
    """Current unix timestamp as float seconds."""
    return time.time()


def utc_ts_int() -> int:
    """Current unix timestamp as integer seconds."""
    return int(time.time())


def monotonic_ts() -> float:
    """Monotonic clock for intervals and scheduling."""
    return time.monotonic()


def expires_in(seconds: float) -> float:
    """Return unix timestamp for now + seconds."""
    return utc_ts() + max(0.0, float(seconds))


def age_seconds(timestamp: float | int | str | None) -> float:
    """Return age in seconds for a unix timestamp."""
    try:
        return max(0.0, utc_ts() - float(timestamp or 0.0))
    except (TypeError, ValueError):
        return float("inf")


def is_expired(expires_at: float | int | str | None) -> bool:
    """Return True if expires_at is present and already passed."""
    if expires_at is None:
        return False

    try:
        return float(expires_at) <= utc_ts()
    except (TypeError, ValueError):
        return True