"""Market selection helpers for choosing the best trading symbol from a snapshot."""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Any, Final

from swarm_config import config

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_SYMBOL: Final[str] = "BTC/USDT"
DEFAULT_EXPECTED_RETURN_RATE: Final[float] = 0.001


def _configured_expected_return_rate() -> float:
    value = getattr(config, "expected_return_rate", DEFAULT_EXPECTED_RETURN_RATE)
    try:
        rate = float(value)
    except (TypeError, ValueError):
        logger.warning("Invalid expected_return_rate=%r; using default %.6f.", value, DEFAULT_EXPECTED_RETURN_RATE)
        return DEFAULT_EXPECTED_RETURN_RATE

    if not math.isfinite(rate) or rate <= 0:
        logger.warning("Non-positive expected_return_rate=%r; using default %.6f.", value, DEFAULT_EXPECTED_RETURN_RATE)
        return DEFAULT_EXPECTED_RETURN_RATE

    return rate


def select_best_market(snapshot: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Select the market with the highest expected score from a snapshot."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a dictionary")

    expected_return_rate = _configured_expected_return_rate()

    best_symbol = ""
    best_tick: dict[str, Any] = {}
    best_score = float("-inf")

    for raw_symbol, raw_tick in snapshot.items():
        symbol = str(raw_symbol or "").strip()
        if not symbol or not isinstance(raw_tick, dict):
            continue

        price = _safe_float(raw_tick.get("price"), 0.0)
        if price <= 0:
            continue

        score = _score_tick(raw_tick, expected_return_rate=expected_return_rate)
        if score > best_score:
            best_score = score
            best_symbol = symbol
            best_tick = dict(raw_tick)

    if not best_symbol:
        return _fallback_market(snapshot)

    best_tick.setdefault("symbol", best_symbol)
    best_tick.setdefault("timestamp", time.time())
    best_tick["selection_score"] = best_score
    return best_symbol, best_tick


def _score_tick(tick: dict[str, Any], *, expected_return_rate: float) -> float:
    price = _safe_float(tick.get("price"), 0.0)
    volatility = max(0.0, _safe_float(tick.get("volatility", tick.get("volatility_estimate")), 0.0))
    liquidity = max(0.0, _safe_float(tick.get("liquidity", tick.get("volume")), 0.0))
    spread = max(0.0, _safe_float(tick.get("spread"), 0.0))

    expected_return = price * expected_return_rate
    liquidity_bonus = math.log1p(liquidity) * 0.0001 if liquidity > 0 else 0.0
    volatility_penalty = price * volatility * 0.05
    spread_penalty = price * spread

    return expected_return + liquidity_bonus - volatility_penalty - spread_penalty


def _fallback_market(snapshot: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if snapshot:
        fallback_symbol = next((str(symbol).strip() for symbol in snapshot.keys() if str(symbol).strip()), "")
        fallback_symbol = fallback_symbol or DEFAULT_FALLBACK_SYMBOL
    else:
        logger.warning("Empty market snapshot provided; using default fallback.")
        fallback_symbol = DEFAULT_FALLBACK_SYMBOL

    fallback_tick = {
        "symbol": fallback_symbol,
        "price": random.uniform(90.0, 110.0),
        "timestamp": time.time(),
        "selection_score": 0.0,
        "fallback": True,
    }
    return fallback_symbol, fallback_tick


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    return number if math.isfinite(number) else default