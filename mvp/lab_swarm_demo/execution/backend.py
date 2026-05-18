"""
Абстрактный интерфейс исполнения сделки.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


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
            symbol (str): The trading pair symbol (e.g., "BTC/USD").
            side (str): The order side, typically "buy" or "sell".
            amount (float): The amount of the base currency to trade.
            price (float): The desired execution price for the order.
            capital (float): The total capital available for the trade.

        Returns:
            Dict[str, Any]: A dictionary containing the result of the order execution.
            Expected keys include:
            - "success" (bool): True if the order was successful, False otherwise.
            - "new_capital" (float): The updated capital after the trade.
            - "tx_hash" (str | None): A transaction hash or identifier if applicable, None otherwise.
            - "status" (str): A string indicating the status of the order (e.g., "filled", "rejected").
            - "error" (str | None): An error message if the order failed, None otherwise.
        """
        ...