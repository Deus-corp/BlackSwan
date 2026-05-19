"""
Abstract interface for trade execution.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ExecutionBackend(ABC):
    """
    Abstract base class defining the interface for executing trade orders.
    Concrete implementations will provide specific logic for simulation or live environments.
    """
    @abstractmethod
    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> Dict[str, Any]:
        """
        Executes a trade order with the specified parameters.

        Args:
            symbol (str): The trading pair symbol (e.g., "BTC/USD", "WETH/USDC").
            side (str): The order side, typically "buy" or "sell".
            amount (float): The amount of the base currency (e.g., BTC in BTC/USD, WETH in WETH/USDC) to trade.
            price (float): The desired execution price for the order.
            capital (float): The total capital available for the trade, typically in the quote currency
                             (e.g., USD in BTC/USD, USDC in WETH/USDC).

        Returns:
            Dict[str, Any]: A dictionary containing the result of the order execution.
            Expected keys include:
            - "success" (bool): True if the order was successful, False otherwise.
            - "new_capital" (float): The updated capital after the trade.
                                     Note: Implementations may provide a placeholder or actual updated value.
            - "tx_hash" (Optional[str]): A transaction hash or identifier if applicable, None otherwise.
            - "status" (str): A string indicating the status of the order (e.g., "filled", "rejected", "skipped", "error").
            - "error" (Optional[str]): An error message if the order failed or was skipped, None otherwise.
        """
        ...