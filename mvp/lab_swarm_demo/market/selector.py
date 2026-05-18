"""
Логика выбора лучшего рынка (символа) для сделки.
"""
import random
from typing import Dict, Tuple, Optional
from swarm_config import config
from typing import Any

EXPECTED_RETURN_RATE: float = config.expected_return_rate


def select_best_market(snapshot: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    Возвращает (symbol, tick_dict) с максимальной ожидаемой доходностью.

    Args:
        snapshot (Dict[str, Dict[str, Any]]): A dictionary where keys are symbols
                                              and values are market tick dictionaries.

    Returns:
        Tuple[str, Dict[str, Any]]: A tuple containing the best symbol and its
                                    corresponding market tick dictionary.
    """
    best_symbol: Optional[str] = None
    best_expected: float = -1.0
    best_tick: Optional[Dict[str, Any]] = None

    for sym, tick in snapshot.items():
        price: float = tick.get("price", 0.0)
        expected: float = price * EXPECTED_RETURN_RATE
        if expected > best_expected:
            best_expected = expected
            best_symbol = sym
            best_tick = tick

    if best_tick is None:
        # крайний случай
        best_symbol = list(snapshot.keys())[0] if snapshot else "WETH/USDC"
        best_tick = {"price": random.uniform(90, 110)}

    # Since best_tick is guaranteed to be set either from snapshot or fallback,
    # we can assert its type to remove Optional.
    return best_symbol, best_tick # type: ignore