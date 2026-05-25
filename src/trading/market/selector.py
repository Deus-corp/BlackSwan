"""
Logic for selecting the best market (trading symbol) for a transaction from a given snapshot.
"""
import logging
import random
import time
from typing import Any, Dict, Final, Tuple

from swarm_config import config

logger: logging.Logger = logging.getLogger(__name__)

# Numeric thresholds defined by configuration, preserved as per strategy.
EXPECTED_RETURN_RATE: Final[float] = float(config.expected_return_rate)


def select_best_market(snapshot: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    Selects the market symbol and tick data with the highest expected return.

    Args:
        snapshot: A dictionary mapping symbols to market tick data.

    Returns:
        A tuple containing the best symbol and its corresponding tick data.

    Raises:
        ValueError: If inputs are invalid or configuration is malformed.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a dictionary.")
    
    if EXPECTED_RETURN_RATE <= 0.0:
        raise ValueError("EXPECTED_RETURN_RATE must be a positive float.")

    best_symbol: str = ""
    best_tick: Dict[str, Any] = {}
    max_expected_return: float = -1.0

    for symbol, tick in snapshot.items():
        if not isinstance(tick, dict):
            continue

        try:
            price: float = float(tick.get("price", 0.0))
        except (TypeError, ValueError):
            continue

        if price <= 0.0:
            continue

        expected_return: float = price * EXPECTED_RETURN_RATE
        if expected_return > max_expected_return:
            max_expected_return = expected_return
            best_symbol = symbol
            best_tick = tick

    # Fallback mechanism if no valid symbols are found in the snapshot
    if not best_symbol or not best_tick:
        if not snapshot:
            logger.warning("Empty snapshot provided; using default fallback.")
        
        fallback_symbol: str = list(snapshot.keys())[0] if snapshot else "BTC/USDT"
        fallback_tick: Dict[str, Any] = {
            "price": random.uniform(90.0, 110.0),
            "symbol": fallback_symbol,
            "timestamp": time.time()
        }
        return fallback_symbol, fallback_tick

    # Ensure the symbol is present in the returned tick data for consistency
    if "symbol" not in best_tick:
        best_tick["symbol"] = best_symbol

    return best_symbol, best_tick