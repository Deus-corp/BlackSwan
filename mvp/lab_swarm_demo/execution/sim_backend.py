"""
Исполнение в симуляции — просто обновляем капитал.
"""
import random
from typing import Dict, Any
from .backend import ExecutionBackend


class SimExecutionBackend(ExecutionBackend):
    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> Dict[str, Any]:
        # Эмулируем простую симуляцию: капитал растёт или падает случайно
        change = price * amount * random.uniform(-0.01, 0.02)
        new_capital = capital + change
        return {
            "success": True,
            "new_capital": new_capital,
            "tx_hash": None,
            "status": "simulated",
            "error": None,
        }