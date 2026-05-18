"""
Исполнение в симуляции — просто обновляем капитал.
"""
import random
from typing import Dict, Any
from .backend import ExecutionBackend


class SimExecutionBackend(ExecutionBackend):
    """
    Backend for simulating order execution.

    It emulates a simple scenario where capital changes randomly based on a trade,
    without actual blockchain interaction.
    """
    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> Dict[str, Any]:
        """
        Simulates the execution of a trading order.

        The capital is updated by a random percentage of the trade value to simulate
        market fluctuations. This method does not interact with any external systems.

        Args:
            symbol: The trading pair symbol (e.g., "WETH/USDC"). Note: This parameter
                    is not directly used in the current implementation logic.
            side: The order side ("buy" or "sell"). Note: This parameter
                  is not directly used in the current implementation logic.
            amount: The amount of the base asset to trade.
            price: The desired price for the trade.
            capital: The current capital available.

        Returns:
            A dictionary containing the result of the simulated order execution,
            including success status, new capital, and simulation status.
        """
        # Эмулируем простую симуляцию: капитал растёт или падает случайно
        change: float = price * amount * random.uniform(-0.01, 0.02)
        new_capital: float = capital + change
        return {
            "success": True,
            "new_capital": new_capital,
            "tx_hash": None,
            "status": "simulated",
            "error": None,
        }