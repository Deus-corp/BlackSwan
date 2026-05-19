"""
Logic for selecting the best market (trading symbol) for a transaction from a given snapshot.
"""
import random
import time
from typing import Dict, Tuple, Optional, Any

# Assuming swarm_config is available and correctly configured
from swarm_config import config

EXPECTED_RETURN_RATE: float = config.expected_return_rate


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
    """
    best_symbol: Optional[str] = None
    best_expected: float = -1.0 # Initialize with a value that any positive return will beat
    best_tick: Optional[Dict[str, Any]] = None

    for sym, tick in snapshot.items():
        # Ensure price is treated as a float, defaulting to 0.0 if not present or invalid.
        # Only consider markets with a positive price for expected return calculation.
        price: float = float(tick.get("price", 0.0))
        if price <= 0.0:
            continue

        expected: float = price * EXPECTED_RETURN_RATE

        if expected > best_expected:
            best_expected = expected
            best_symbol = sym
            best_tick = tick

    if best_tick is None:
        # Fallback case: if no market with a positive expected return was found
        # (e.g., snapshot was empty, or all prices were 0 or negative).
        # We ensure a default market is returned for continued operation.
        fallback_symbol: str = list(snapshot.keys())[0] if snapshot else "BTC/USDT" # Use a common default
        # The fallback tick should mimic the structure expected from the snapshot service.
        fallback_tick: Dict[str, Any] = {
            "price": random.uniform(90.0, 110.0), # Use floats for uniformity
            "symbol": fallback_symbol,
            "timestamp": time.time() # Add timestamp for completeness
        }
        return fallback_symbol, fallback_tick
    else:
        # At this point, best_tick and best_symbol are guaranteed not to be None.
        # Add the symbol to the best_tick for consistency, if not already present.
        # The snapshot service's fallback already includes it, but adapter data might vary.
        if "symbol" not in best_tick:
            best_tick["symbol"] = best_symbol
        return best_symbol, best_tick
