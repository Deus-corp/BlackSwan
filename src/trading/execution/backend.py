"""
Abstract interface for trade execution modules.

This module defines the contract for trade execution backends, enabling
interchangeable use of live exchange integrations and simulation environments.
"""
from abc import ABC, abstractmethod
from typing import Final, Literal, TypedDict, Optional


class ExecutionResult(TypedDict):
    """
    Typed dictionary defining the required response structure for trade execution.
    """
    success: bool
    new_capital: float
    status: Literal["filled", "rejected", "skipped", "error", "simulated"]
    tx_hash: Optional[str]
    error: Optional[str]


class ExecutionBackend(ABC):
    """
    Abstract base class defining the interface for executing trade orders.

    Concrete implementations must handle the specific API or simulation logic required
    to bridge the execution engine with the target exchange or market environment.
    """

    @abstractmethod
    async def execute_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        amount: float,
        price: float,
        capital: float,
    ) -> ExecutionResult:
        """
        Executes a trade order with the specified parameters.

        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD").
            side: The order side, either "buy" or "sell".
            amount: The quantity of the base currency to trade.
            price: The price at which the order is executed.
            capital: The total capital available for the trade in quote currency.

        Returns:
            ExecutionResult: A dictionary containing the outcome of the order execution.
        """
        ...