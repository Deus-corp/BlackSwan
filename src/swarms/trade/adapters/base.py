"""Base adapter contracts and helpers."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SystemAdapterProtocol(Protocol):
    """Runtime-checkable protocol for command adapters."""

    def execute(self, command: str) -> dict[str, Any]:
        ...


class SystemAdapter(ABC):
    """Abstract base class for adapters that execute string commands."""

    @abstractmethod
    def execute(self, command: str) -> dict[str, Any]:
        """Execute a command and return a normalized result."""
        raise NotImplementedError

    async def execute_async(self, command: str) -> dict[str, Any]:
        """Async-compatible wrapper around execute()."""
        result = self.execute(command)
        if inspect.isawaitable(result):
            result = await result

        if not isinstance(result, dict):
            return {
                "success": False,
                "status": "error",
                "error": f"adapter returned {type(result).__name__}, expected dict",
            }

        return result


def normalize_adapter_result(
    result: Any,
    *,
    default_status: str = "ok",
) -> dict[str, Any]:
    """Normalize arbitrary adapter output into a dictionary."""
    if isinstance(result, dict):
        normalized = dict(result)
        normalized.setdefault("success", not bool(normalized.get("error")))
        normalized.setdefault("status", default_status if normalized["success"] else "error")
        normalized.setdefault("error", None if normalized["success"] else str(normalized.get("error") or "adapter_error"))
        return normalized

    return {
        "success": result is not None,
        "status": default_status if result is not None else "error",
        "result": result,
        "error": None if result is not None else "adapter_returned_none",
    }