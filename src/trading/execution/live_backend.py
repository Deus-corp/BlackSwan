"""Live/Web3 trade execution backend."""

from __future__ import annotations

import inspect
import logging
import math
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from web3 import Web3

from .backend import ExecutionBackend, ExecutionResult, OrderSide, error_result, rejected_result, skipped_result

logger = logging.getLogger(__name__)

WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"


@runtime_checkable
class Web3AdapterProtocol(Protocol):
    """Expected live/Web3 adapter interface."""

    w3: Web3

    async def _get_token_balance(self, token_address: str) -> float:
        ...

    async def place_order(self, side: str, amount: float, price: float) -> dict[str, Any]:
        ...


class LiveExecutionBackend(ExecutionBackend):
    """Backend for guarded live/Web3 execution."""

    def __init__(
        self,
        node_id: str,
        adapter: Web3AdapterProtocol | Any,
        is_leader_func: Callable[[int], bool],
    ) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")
        if adapter is None:
            raise ValueError("adapter is required")
        if not callable(is_leader_func):
            raise TypeError("is_leader_func must be callable")

        self.node_id = clean_node_id
        self.adapter = adapter
        self.is_leader_func = is_leader_func

    async def execute_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        price: float,
        capital: float,
    ) -> ExecutionResult:
        """Execute a guarded live order through the configured adapter."""
        capital_value = self._safe_float(capital, 0.0)
        clean_symbol = str(symbol or "").strip()
        clean_side = str(side or "").strip().lower()

        if not clean_symbol:
            return rejected_result(capital_value, "symbol_required")
        if clean_side not in {"buy", "sell"}:
            return rejected_result(capital_value, f"unsupported_side:{side}")

        amount_value = self._safe_positive(amount, "amount")
        price_value = self._safe_positive(price, "price")
        if amount_value is None:
            return rejected_result(capital_value, "amount_must_be_positive")
        if price_value is None:
            return rejected_result(capital_value, "price_must_be_positive")

        if not self._adapter_ready():
            logger.error("[%s] LiveExecutionBackend requires adapter.place_order().", self.node_id)
            return error_result(capital_value, "adapter_missing_place_order")

        adjusted_amount = await self._adjust_amount_for_balance(clean_symbol, clean_side, amount_value)
        if adjusted_amount <= 0:
            return rejected_result(capital_value, "insufficient_balance_or_zero_amount")

        leader_result = await self._leader_check()
        if not leader_result["allowed"]:
            status = "skipped" if leader_result["error"] == "not_leader" else "rejected"
            if status == "skipped":
                return skipped_result(capital_value, leader_result["error"])
            return rejected_result(capital_value, leader_result["error"])

        try:
            result = await self._call_place_order(
                symbol=clean_symbol,
                side=clean_side,
                amount=adjusted_amount,
                price=price_value,
            )
        except Exception as exc:
            logger.exception("[%s] Live order execution failed unexpectedly.", self.node_id)
            return error_result(capital_value, str(exc))

        return self._normalize_adapter_result(result, capital_value)

    def _adapter_ready(self) -> bool:
        return callable(getattr(self.adapter, "place_order", None))

    async def _adjust_amount_for_balance(self, symbol: str, side: str, amount: float) -> float:
        if side != "sell":
            return amount

        get_balance = getattr(self.adapter, "_get_token_balance", None)
        if not callable(get_balance):
            logger.warning("[%s] Adapter has no _get_token_balance(); sell balance check skipped.", self.node_id)
            return amount

        token_address = self._base_token_address(symbol)

        try:
            balance = await self._maybe_await(get_balance(token_address))
            balance_value = max(0.0, self._safe_float(balance, 0.0))
            adjusted = min(amount, balance_value)

            logger.debug(
                "[%s] Sell balance check symbol=%s balance=%.8f requested=%.8f adjusted=%.8f",
                self.node_id,
                symbol,
                balance_value,
                amount,
                adjusted,
            )
            return adjusted

        except Exception as exc:
            logger.warning("[%s] Sell balance check failed; refusing sell: %s", self.node_id, exc)
            return 0.0

    async def _leader_check(self) -> dict[str, Any]:
        try:
            block_number = await self._current_block_number()
        except Exception as exc:
            logger.warning("[%s] Leader check failed; refusing live execution: %s", self.node_id, exc)
            return {"allowed": False, "error": "leader_check_failed", "block_number": None}

        try:
            is_leader = bool(self.is_leader_func(int(block_number)))
        except Exception as exc:
            logger.warning(
                "[%s] Leader predicate failed for block=%s; refusing live execution: %s",
                self.node_id,
                block_number,
                exc,
            )
            return {"allowed": False, "error": "leader_check_failed", "block_number": int(block_number)}

        if not is_leader:
            logger.info("[%s] Skipping live execution: not leader for block %s.", self.node_id, block_number)
            return {"allowed": False, "error": "not_leader", "block_number": int(block_number)}

        return {"allowed": True, "error": "", "block_number": int(block_number)}

    async def _current_block_number(self) -> int:
        w3 = getattr(self.adapter, "w3", None)
        eth = getattr(w3, "eth", None)
        if eth is None:
            raise RuntimeError("adapter_missing_w3_eth")

        try:
            block_number_attr = getattr(eth, "block_number")
        except AttributeError as exc:
            raise RuntimeError("adapter_missing_w3_eth_block_number") from exc

        block_number = await self._maybe_await(block_number_attr)
        return int(block_number)

    async def _call_place_order(self, *, symbol: str, side: str, amount: float, price: float) -> dict[str, Any]:
        place_order = getattr(self.adapter, "place_order")

        try:
            result = place_order(symbol=symbol, side=side, amount=amount, price=price)
        except TypeError:
            result = place_order(side=side, amount=amount, price=price)

        result = await self._maybe_await(result)
        if not isinstance(result, dict):
            raise TypeError(f"adapter.place_order returned {type(result).__name__}, expected dict")

        return result

    def _normalize_adapter_result(self, result: dict[str, Any], capital: float) -> ExecutionResult:
        raw_status = str(result.get("status", "") or "").strip().lower()
        success = bool(result.get("success", False)) or raw_status in {"success", "filled", "simulated"}

        tx_hash = result.get("tx_hash") or result.get("transaction_hash") or result.get("hash")
        tx_hash_text = str(tx_hash) if tx_hash else None

        if success:
            logger.info("[%s] Live order filled. tx_hash=%s", self.node_id, tx_hash_text)
            return {
                "success": True,
                "new_capital": self._safe_float(result.get("new_capital"), capital),
                "tx_hash": tx_hash_text,
                "status": "filled",
                "error": None,
            }

        error = str(result.get("error") or result.get("reason") or "live_order_failed")
        logger.error("[%s] Live order failed: %s result=%s", self.node_id, error, result)

        status = "rejected" if raw_status in {"rejected", "failed", "failure"} else "error"
        return {
            "success": False,
            "new_capital": capital,
            "tx_hash": tx_hash_text,
            "status": status,
            "error": error,
        }

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _base_token_address(symbol: str) -> str:
        base = str(symbol or "").split("/", 1)[0].strip().upper()
        if base == "WETH":
            return WETH_ADDRESS
        if base == "USDC":
            return USDC_ADDRESS
        return WETH_ADDRESS

    @staticmethod
    def _safe_positive(value: Any, name: str) -> float | None:
        number = LiveExecutionBackend._safe_float(value, float("nan"))
        if not math.isfinite(number) or number <= 0:
            logger.warning("%s must be positive finite number, got %r", name, value)
            return None
        return number

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default