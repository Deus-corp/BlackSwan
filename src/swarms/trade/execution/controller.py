"""TradingController — on-chain trading helpers for swaps and balance rebalancing."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from loguru import logger

try:
    from swarm_config import config
except ImportError:
    config = None  # type: ignore[assignment]

try:
    from src.swarms.trade.adapters.web3_testnet import USDC_ADDRESS, WETH_ADDRESS
except ImportError:
    WETH_ADDRESS = ""
    USDC_ADDRESS = ""


class Web3AdapterProtocol(Protocol):
    """Expected interface for the trading Web3 adapter."""

    w3: Any
    account: Any

    async def _get_token_balance(self, token_address: str) -> float:
        ...

    async def wrap_eth(self, amount: float) -> dict[str, Any]:
        ...

    async def unwrap_weth(self, amount: float) -> dict[str, Any]:
        ...

    async def place_order(
        self,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> dict[str, Any]:
        ...


class TradingController:
    """Handles balance checks, rebalancing, swaps, and simple trade decisions."""

    DEFAULT_MIN_WETH_BALANCE = 0.1
    DEFAULT_MIN_ETH_BALANCE = 0.05
    DEFAULT_MAX_USDC_BALANCE = 100.0
    DEFAULT_WRAP_UNWRAP_BUFFER = 0.0005
    DEFAULT_WRAP_UNWRAP_AMOUNT = 0.001
    DEFAULT_USDC_SWAP_AMOUNT_WETH = 0.002
    DEFAULT_EXPECTED_RETURN_RATE = 0.01
    DEFAULT_DECISION_THRESHOLD_FACTOR = 0.001
    DEFAULT_MAX_RISK_PER_TRADE = 0.05

    def __init__(self, node_id: str) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.node_id = clean_node_id

    async def check_and_rebalance(self, adapter: Web3AdapterProtocol) -> bool:
        """Check balances and initiate at most one rebalance action."""
        if not self._adapter_ready(adapter):
            logger.warning("[%s] Adapter/account unavailable for rebalance check.", self.node_id)
            return False

        if not WETH_ADDRESS or not USDC_ADDRESS:
            logger.warning("[%s] Token addresses unavailable for rebalance check.", self.node_id)
            return False

        try:
            weth_bal = await self._token_balance(adapter, WETH_ADDRESS)
            usdc_bal = await self._token_balance(adapter, USDC_ADDRESS)
            eth_bal = await self._eth_balance(adapter)

            min_weth = self._config_float("min_weth_balance", self.DEFAULT_MIN_WETH_BALANCE)
            min_eth = self._config_float("min_eth_balance", self.DEFAULT_MIN_ETH_BALANCE)
            max_usdc = self._config_float("max_usdc_balance", self.DEFAULT_MAX_USDC_BALANCE)

            logger.debug(
                "[%s] Balances: ETH=%.4f, WETH=%.4f, USDC=%.4f",
                self.node_id,
                eth_bal,
                weth_bal,
                usdc_bal,
            )

            if usdc_bal > max_usdc and weth_bal < min_weth:
                amount = self.DEFAULT_USDC_SWAP_AMOUNT_WETH
                logger.info(
                    "[%s] USDC surplus %.4f > %.4f and WETH low %.4f < %.4f; buying %.6f WETH.",
                    self.node_id,
                    usdc_bal,
                    max_usdc,
                    weth_bal,
                    min_weth,
                    amount,
                )
                result = await adapter.place_order("buy", amount)
                logger.info("[%s] USDC->WETH rebalance result: %s", self.node_id, result)
                return self._result_success_or_attempted(result)

            if weth_bal < min_weth and eth_bal > min_eth + self.DEFAULT_WRAP_UNWRAP_BUFFER:
                amount = min(
                    self.DEFAULT_WRAP_UNWRAP_AMOUNT,
                    max(0.0, eth_bal - min_eth - self.DEFAULT_WRAP_UNWRAP_BUFFER),
                    max(self.DEFAULT_WRAP_UNWRAP_AMOUNT, min_weth - weth_bal),
                )
                if amount > 0:
                    logger.info(
                        "[%s] WETH low %.4f < %.4f; wrapping %.6f ETH.",
                        self.node_id,
                        weth_bal,
                        min_weth,
                        amount,
                    )
                    result = await adapter.wrap_eth(amount)
                    logger.info("[%s] Wrap result: %s", self.node_id, result)
                    return self._result_success_or_attempted(result)

            if eth_bal < min_eth and weth_bal > min_weth + self.DEFAULT_WRAP_UNWRAP_BUFFER:
                amount = min(
                    self.DEFAULT_WRAP_UNWRAP_AMOUNT,
                    max(0.0, weth_bal - min_weth - self.DEFAULT_WRAP_UNWRAP_BUFFER),
                    max(self.DEFAULT_WRAP_UNWRAP_AMOUNT, min_eth - eth_bal),
                )
                if amount > 0:
                    logger.info(
                        "[%s] ETH low %.4f < %.4f; unwrapping %.6f WETH.",
                        self.node_id,
                        eth_bal,
                        min_eth,
                        amount,
                    )
                    result = await adapter.unwrap_weth(amount)
                    logger.info("[%s] Unwrap result: %s", self.node_id, result)
                    return self._result_success_or_attempted(result)

        except Exception as exc:
            logger.error("[%s] Rebalance error: %s", self.node_id, exc, exc_info=True)

        return False

    async def execute_swap(
        self,
        adapter: Web3AdapterProtocol,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> dict[str, Any]:
        """Execute a swap through the adapter."""
        clean_side = str(side or "").strip().lower()
        if clean_side not in {"buy", "sell"}:
            return {"success": False, "error": "side must be 'buy' or 'sell'"}

        clean_amount = self._safe_float(amount)
        if clean_amount <= 0:
            return {"success": False, "error": "amount must be positive"}

        if not self._adapter_ready(adapter):
            return {"success": False, "error": "adapter/account unavailable"}

        try:
            logger.info(
                "[%s] Executing %s swap amount=%.8f price=%s",
                self.node_id,
                clean_side,
                clean_amount,
                price if price is not None else "market",
            )
            result = await adapter.place_order(clean_side, clean_amount, price=price)
            logger.info("[%s] Swap result: %s", self.node_id, result)
            return dict(result) if isinstance(result, dict) else {"success": True, "result": result}
        except Exception as exc:
            logger.error("[%s] Swap exception: %s", self.node_id, exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def decide_action(
        self,
        market: dict[str, Any],
        current_params: dict[str, float],
        capital: float,
        _step: int,
        orderbook_imbalance: float = 0.0,
        orderbook_delta_volume: float = 0.0,
    ) -> dict[str, float | str]:
        """Return a simple directional action and position size."""
        price = max(0.0, self._safe_float(market.get("price", 100.0), 100.0))
        capital_value = max(0.0, self._safe_float(capital, 0.0))
        max_risk = self._clamp(
            self._safe_float(current_params.get("max_risk_per_trade"), self.DEFAULT_MAX_RISK_PER_TRADE),
            0.0,
            1.0,
        )

        expected_return_rate = self._config_float(
            "expected_return_rate",
            self.DEFAULT_EXPECTED_RETURN_RATE,
        )
        threshold_factor = self._config_float(
            "decision_threshold_factor",
            self.DEFAULT_DECISION_THRESHOLD_FACTOR,
        )

        expected_return = price * expected_return_rate
        decision_threshold = price * threshold_factor

        side = "buy" if expected_return > decision_threshold else "sell"
        amount = (capital_value * max_risk) / price if price > 0 else 0.0

        imbalance = self._safe_float(orderbook_imbalance, 0.0)
        delta_volume = self._safe_float(orderbook_delta_volume, 0.0)

        if side == "buy" and imbalance < -0.1:
            logger.debug("[%s] Reducing buy size due to sell pressure %.3f.", self.node_id, imbalance)
            amount *= 0.6
        elif side == "sell" and imbalance > 0.1:
            logger.debug("[%s] Reducing sell size due to buy pressure %.3f.", self.node_id, imbalance)
            amount *= 0.6

        if delta_volume < 0:
            amount *= 0.9

        return {
            "action": side,
            "amount": max(0.0, amount),
        }

    async def _token_balance(self, adapter: Web3AdapterProtocol, token_address: str) -> float:
        return max(0.0, self._safe_float(await adapter._get_token_balance(token_address), 0.0))

    async def _eth_balance(self, adapter: Web3AdapterProtocol) -> float:
        eth_wei = await adapter.w3.eth.get_balance(adapter.account.address)
        return max(0.0, self._safe_float(adapter.w3.from_wei(eth_wei, "ether"), 0.0))

    @staticmethod
    def _adapter_ready(adapter: Any) -> bool:
        return bool(adapter and getattr(adapter, "account", None) and getattr(adapter.account, "address", None))

    @staticmethod
    def _result_success_or_attempted(result: Any) -> bool:
        if not isinstance(result, dict):
            return True
        if "success" in result:
            return bool(result.get("success"))
        if "error" in result:
            return False
        return True

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _config_float(name: str, default: float) -> float:
        if config is None:
            return default

        trading_config = getattr(config, "trading", None)
        value = getattr(trading_config, name, None) if trading_config is not None else None

        if value is None:
            value = getattr(config, name, default)

        try:
            return float(value)
        except (TypeError, ValueError):
            return default