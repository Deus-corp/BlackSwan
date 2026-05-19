"""
Execution in simulation – simply update capital.
"""
import random
from typing import Dict, Any
from .backend import ExecutionBackend


class SimExecutionBackend(ExecutionBackend):
    """
    Backend for simulating order execution.

    It emulates a simple scenario where capital changes randomly based on a trade,
    without actual blockchain interaction. This is primarily for testing and
    development of strategies in a controlled, predictable environment.
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
            symbol (str): The trading pair symbol (e.g., "WETH/USDC"). Note: This parameter
                          is not directly used in the current implementation logic.
            side (str): The order side ("buy" or "sell"). Note: This parameter
                        is not directly used in the current implementation logic.
            amount (float): The amount of the base asset to trade.
            price (float): The desired price for the trade.
            capital (float): The current capital available.

        Returns:
            Dict[str, Any]: A dictionary containing the result of the simulated order execution,
            including success status, new capital, and simulation status.
            Example:
            {
                "success": True,
                "new_capital": 1005.50,
                "tx_hash": None,
                "status": "simulated",
                "error": None,
            }
        """
        # Emulate a simple simulation: capital grows or falls randomly
        # The change is based on a random percentage of the trade value (price * amount).
        # It ranges from -1% to +2% of the trade value.
        trade_value: float = price * amount
        change_percentage: float = random.uniform(-0.01, 0.02)
        change: float = trade_value * change_percentage
        
        new_capital: float = capital + change
        
        return {
            "success": True,
            "new_capital": new_capital,
            "tx_hash": None,  # No transaction hash in simulation
            "status": "simulated",
            "error": None,
        }