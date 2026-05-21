"""
Logic for selecting the best market (trading symbol) for a transaction from a given snapshot.
"""
import random
import time
from typing import Dict, Tuple, Optional, Any, Final, cast

from swarm_config import config

EXPECTED_RETURN_RATE: Final[float] = config.expected_return_rate


def select_best_market(snapshot: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    Selects the market (symbol and its tick data) with the maximum expected return.

    Iterates through a market snapshot to find the symbol (market) with the highest
    expected return based on its 'price' and a predefined `EXPECTED_RETURN_RATE`.
    Only markets with positive prices are considered for potential returns.
    If no suitable market is found (e.g., empty snapshot, all prices non-positive),
    it falls back to a default/simulated market.

    Args:
        snapshot: A dictionary where keys are symbols (e.g., "WETH/USDC") and values are
                  market tick dictionaries. Each tick dictionary is expected to
                  contain at least a "price" key.

    Returns:
        A tuple containing:
        - The symbol (str) of the best market.
        - The corresponding market tick dictionary (Dict[str, Any]). This dictionary
          will always contain at least "price" and "symbol" keys, even in fallback scenarios.

    Raises:
        ValueError: If `snapshot` is not a dictionary or if `EXPECTED_RETURN_RATE` is not positive.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a dictionary.")
    if EXPECTED_RETURN_RATE <= 0.0:
        raise ValueError("EXPECTED_RETURN_RATE must be a positive float.")

    best_symbol: Optional[str] = None
    best_expected: float = -1.0
    best_tick: Optional[Dict[str, Any]] = None

    for sym, tick in snapshot.items():
        if not isinstance(tick, dict):
            continue
        try:
            price: float = float(tick.get("price", 0.0))
        except (TypeError, ValueError):
            continue
        if price <= 0.0:
            continue

        expected: float = price * EXPECTED_RETURN_RATE

        if expected > best_expected:
            best_expected = expected
            best_symbol = sym
            best_tick = tick

    if best_tick is None or best_symbol is None:
        fallback_symbol: str = list(snapshot.keys())[0] if snapshot else "BTC/USDT"
        if not snapshot:
            logger.warning("Empty snapshot provided, using default fallback symbol.")
        fallback_tick: Dict[str, Any] = {
            "price": random.uniform(90.0, 110.0),
            "symbol": fallback_symbol,
            "timestamp": time.time()
        }
        return fallback_symbol, fallback_tick
    else:
        if "symbol" not in best_tick:
            best_tick["symbol"] = best_symbol
        return best_symbol, best_tick


logger = logging.getLogger(__name__)