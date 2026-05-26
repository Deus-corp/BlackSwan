"""Centralized type definitions and runtime contracts for core domain objects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, TypeGuard, runtime_checkable


@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for swarm configuration objects."""

    def validate(self) -> bool:
        ...


@runtime_checkable
class CRDTProtocol(Protocol):
    """Minimal CRDT adapter contract used by swarm services."""

    async def add_genome(self, genome: dict[str, Any]) -> Any:
        ...

    async def get_top(self, limit: int = 10) -> list[dict[str, Any]]:
        ...


@runtime_checkable
class EventStoreProtocol(Protocol):
    """Minimal append-only event store contract."""

    def append(self, event: Any) -> None:
        ...


@runtime_checkable
class TelegramNotifierProtocol(Protocol):
    """Minimal async notifier contract."""

    async def send(self, message: str) -> bool:
        ...


@runtime_checkable
class MarketAdapterProtocol(Protocol):
    """Minimal market data adapter contract."""

    async def fetch_all_tickers(self) -> dict[str, dict[str, Any]] | None:
        ...


@runtime_checkable
class ExecutionAdapterProtocol(Protocol):
    """Minimal execution adapter contract."""

    async def place_order(self, side: str, amount: float, price: float) -> dict[str, Any]:
        ...


LeadershipFunc = Callable[[int], bool]
AsyncCallback = Callable[..., Awaitable[Any]]
JSONMapping = Mapping[str, Any]


def has_validate(obj: Any) -> TypeGuard[ConfigProtocol]:
    """Return True when object satisfies ConfigProtocol at runtime."""
    return callable(getattr(obj, "validate", None))


def has_crdt_methods(obj: Any) -> TypeGuard[CRDTProtocol]:
    """Return True when object exposes the minimal CRDT adapter methods."""
    return callable(getattr(obj, "add_genome", None)) and callable(getattr(obj, "get_top", None))


def has_market_adapter_methods(obj: Any) -> TypeGuard[MarketAdapterProtocol]:
    """Return True when object exposes fetch_all_tickers()."""
    return callable(getattr(obj, "fetch_all_tickers", None))


def has_execution_adapter_methods(obj: Any) -> TypeGuard[ExecutionAdapterProtocol]:
    """Return True when object exposes place_order()."""
    return callable(getattr(obj, "place_order", None))