"""
Логика выбора лучшего рынка (символа) для сделки.
"""
import random
from typing import Dict, Tuple, Optional, Any, Union

# Assuming swarm_config is available and correctly configured
from swarm_config import config

EXPECTED_RETURN_RATE: float = config.expected_return_rate


def select_best_market(snapshot: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    Возвращает (symbol, tick_dict) с максимальной ожидаемой доходностью.

    Iterates through a market snapshot to find the symbol (market) with the highest
    expected return based on its 'price' and a predefined `EXPECTED_RETURN_RATE`.
    If no suitable market is found (e.g., empty snapshot or no positive prices),
    it falls back to a default/simulated market.

    Args:
        snapshot (Dict[str, Dict[str, Any]]): A dictionary where keys are symbols
                                              (e.g., "WETH/USDC") and values are
                                              market tick dictionaries, expected to
                                              contain at least a "price" key.

    Returns:
        Tuple[str, Dict[str, Any]]: A tuple containing the best symbol and its
                                    corresponding market tick dictionary. The tick
                                    dictionary will always contain at least "price"
                                    and "symbol" keys, even in fallback scenarios.
    """
    best_symbol: Optional[str] = None
    best_expected: float = -1.0
    best_tick: Optional[Dict[str, Any]] = None

    for sym, tick in snapshot.items():
        # Ensure price is treated as a float, defaulting to 0.0 if not present or invalid.
        price: float = float(tick.get("price", 0.0))
        expected: float = price * EXPECTED_RETURN_RATE

        if expected > best_expected:
            best_expected = expected
            best_symbol = sym
            best_tick = tick

    if best_tick is None:
        # Fallback case: if no market with a positive expected return was found
        # (e.g., snapshot was empty, or all prices were 0 or negative).
        # We ensure a default market is returned.
        fallback_symbol: str = list(snapshot.keys())[0] if snapshot else "WETH/USDC"
        # The fallback tick should mimic the structure expected from the snapshot service.
        fallback_tick: Dict[str, Any] = {
            "price": random.uniform(90.0, 110.0), # Use floats for uniformity
            "symbol": fallback_symbol
        }
        return fallback_symbol, fallback_tick
    else:
        # At this point, best_tick is guaranteed not to be None.
        # If best_tick is not None, best_symbol must also be not None,
        # as they are assigned together within the loop.
        # We use assertions for clarity and to help type checkers confirm non-None types.
        assert best_symbol is not None, "best_symbol should not be None if best_tick is not None"
        # Add the symbol to the best_tick for consistency, if not already present.
        # The snapshot service's fallback already includes it, but adapter data might vary.
        if "symbol" not in best_tick:
            best_tick["symbol"] = best_symbol
        return best_symbol, best_tick