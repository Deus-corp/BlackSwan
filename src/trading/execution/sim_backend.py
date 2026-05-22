"""
Execution backend implementation for simulated trading environments.
"""

import random
from typing import Any, Dict, TypedDict
from .backend import ExecutionBackend

class ExecutionResult(TypedDict):
    """Type definition for order execution results."""
    success: bool
    new_capital: float
    tx_hash: str | None
    status: str
    error: str | None

class SimExecutionBackend(ExecutionBackend):
    """
    Backend for simulating order execution without blockchain interaction.

    This implementation emulates market fluctuations by applying a random
    percentage change to the trade value, allowing for deterministic or
    stochastic strategy testing.
    """

    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> ExecutionResult:
        """
        Simulate the execution of a trading order.

        The capital is adjusted by a random factor between -1% and +2% of the
        total trade value to simulate market volatility.

        Args:
            symbol: The trading pair identifier (e.g., "WETH/USDC").
            side: The order direction ("buy" or "sell").
            amount: The quantity of the base asset being traded.
            price: The reference price for the execution.
            capital: The current capital available for trading.

        Returns:
            ExecutionResult: A dictionary containing the simulated execution outcome.
        """
        trade_value = price * amount
        
        # Generate a random fluctuation factor between -0.01 and 0.02
        fluctuation = random.uniform(-0.01, 0.02)
        capital_adjustment = trade_value * fluctuation
        
        return {
            "success": True,
            "new_capital": capital + capital_adjustment,
            "tx_hash": None,
            "status": "simulated",
            "error": None,
        }