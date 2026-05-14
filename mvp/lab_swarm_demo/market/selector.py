"""
Логика выбора лучшего рынка (символа) для сделки.
"""
import random
from typing import Dict, Tuple, Optional
from swarm_config import config

EXPECTED_RETURN_RATE = config.expected_return_rate


def select_best_market(snapshot: Dict[str, dict]) -> Tuple[str, dict]:
    """
    Возвращает (symbol, tick_dict) с максимальной ожидаемой доходностью.
    """
    best_symbol = None
    best_expected = -1.0
    best_tick = None

    for sym, tick in snapshot.items():
        price = tick.get("price", 0.0)
        expected = price * EXPECTED_RETURN_RATE
        if expected > best_expected:
            best_expected = expected
            best_symbol = sym
            best_tick = tick

    if best_tick is None:
        # крайний случай
        best_symbol = list(snapshot.keys())[0] if snapshot else "WETH/USDC"
        best_tick = {"price": random.uniform(90, 110)}

    return best_symbol, best_tick