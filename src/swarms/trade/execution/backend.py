"""Abstract interface and helpers for trade execution backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional, TypedDict


OrderSide = Literal["buy", "sell"]
ExecutionStatus = Literal["filled", "rejected", "skipped", "error", "simulated"]


class ExecutionResult(TypedDict):
    """Required response structure for trade execution."""

    success: bool
    new_capital: float
    status: ExecutionStatus
    tx_hash: Optional[str]
    error: Optional[str]


class ExecutionBackend(ABC):
    """Abstract base class for live and simulated order execution backends."""

    @abstractmethod
    async def execute_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        price: float,
        capital: float,
    ) -> ExecutionResult:
        """Execute an order and return normalized execution result."""
        ...


def make_execution_result(
    *,
    success: bool,
    new_capital: float,
    status: ExecutionStatus,
    tx_hash: Optional[str] = None,
    error: Optional[str] = None,
) -> ExecutionResult:
    """Build a normalized ExecutionResult."""
    return {
        "success": bool(success),
        "new_capital": float(new_capital),
        "status": status,
        "tx_hash": tx_hash,
        "error": error,
    }


def rejected_result(capital: float, error: str) -> ExecutionResult:
    """Return a standardized rejected execution result."""
    return make_execution_result(
        success=False,
        new_capital=capital,
        status="rejected",
        error=str(error),
    )


def error_result(capital: float, error: str) -> ExecutionResult:
    """Return a standardized error execution result."""
    return make_execution_result(
        success=False,
        new_capital=capital,
        status="error",
        error=str(error),
    )


def skipped_result(capital: float, reason: str = "skipped") -> ExecutionResult:
    """Return a standardized skipped execution result."""
    return make_execution_result(
        success=False,
        new_capital=capital,
        status="skipped",
        error=str(reason),
    )