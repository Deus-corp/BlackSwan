"""
TradingController — ончейн-торговля: свопы, авто-конвертация USDC, wrap/unwrap,
принятие решений о входе с учётом ордербука.
"""
from typing import Any, Dict, Optional
from loguru import logger
# Assuming swarm_config and adapters.web3_testnet are available and correctly defined
from swarm_config import config
from adapters.web3_testnet import WETH_ADDRESS, USDC_ADDRESS


# Define a minimal protocol for the adapter to provide type hinting if its full class is not available
# This is an optional improvement if the adapter type is complex or external.
# For simplicity, using `Any` for the adapter parameter in this context.

class TradingController:
    """
    Handles on-chain trading operations including swaps, USDC auto-conversion,
    ETH wrap/unwrap, and making trading decisions based on market data and orderbook.
    """
    def __init__(self, node_id: str):
        """
        Initializes the TradingController with a unique node identifier.

        Args:
            node_id: A string identifier for the trading node.
        """
        self.node_id = node_id

    # ------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------
    async def check_and_rebalance(self, adapter: Any) -> bool:
        """
        Проверяет балансы и при необходимости выполняет конвертацию или wrap/unwrap.
        Возвращает True, если была выполнена транзакция.

        Args:
            adapter: An adapter object that provides blockchain interaction methods
                     like `_get_token_balance`, `w3`, `account`, `wrap_eth`, `unwrap_weth`, `place_order`.
        Returns:
            True if a rebalancing transaction was initiated, False otherwise.
        """
        if not adapter or not adapter.account:
            logger.warning(f"[{self.node_id}] Adapter or account not available for rebalance check.")
            return False

        try:
            weth_bal: float = await adapter._get_token_balance(WETH_ADDRESS)
            eth_wei: int = await adapter.w3.eth.get_balance(adapter.account.address)
            eth_bal: float = float(adapter.w3.from_wei(eth_wei, 'ether'))
            usdc_bal: float = await adapter._get_token_balance(USDC_ADDRESS)

            min_weth: float = config.trading.min_weth_balance
            min_eth: float = config.trading.min_eth_balance
            max_usdc: float = config.trading.max_usdc_balance

            # Приоритет: избыток USDC → покупаем WETH
            if usdc_bal > max_usdc and weth_bal < min_weth:
                logger.info(f"[{self.node_id}] USDC surplus ({usdc_bal:.4f}), buying WETH")
                # The amount for place_order should be dynamic, but fixed here for example
                result: Dict[str, Any] = await adapter.place_order("buy", 0.002)
                logger.info(f"USDC->WETH swap result: {result}")
                return True

            # Wrap при нехватке WETH
            if weth_bal < min_weth and eth_bal > min_eth + 0.0005:
                logger.info(f"[{self.node_id}] WETH low ({weth_bal:.4f}), wrapping 0.0005 ETH")
                await adapter.wrap_eth(0.0005)
                return True

            # Unwrap при нехватке ETH
            if eth_bal < min_eth and weth_bal > min_weth + 0.0005:
                logger.info(f"[{self.node_id}] ETH low ({eth_bal:.4f}), unwrapping 0.0005 WETH")
                await adapter.unwrap_weth(0.0005)
                return True

        except Exception as e:
            logger.error(f"[{self.node_id}] Rebalance error: {e}", exc_info=True)
        return False

    async def execute_swap(self, adapter: Any, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Выполняет одиночный своп.

        Args:
            adapter: The blockchain interaction adapter.
            side: The type of trade, "buy" or "sell".
            amount: The amount of asset to trade.
            price: Optional. The price at which to execute the trade.
        Returns:
            A dictionary containing the result of the swap, or an error message.
        """
        try:
            result: Dict[str, Any] = await adapter.place_order(side, amount, price=price)
            logger.info(f"[{self.node_id}] Swap result: {result}")
            return result
        except Exception as e:
            logger.error(f"[{self.node_id}] Swap exception: {e}", exc_info=True)
            return {"error": str(e)}

    # ------------------------------------------------------------
    # Принятие торгового решения (вызывается из основного цикла)
    # ------------------------------------------------------------
    def decide_action(
        self,
        market: Dict[str, Any],
        current_params: Dict[str, float],
        capital: float,
        step: int,
        orderbook_imbalance: float = 0.0,
        orderbook_delta_volume: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Возвращает словарь с ключами 'action' (buy/sell) и 'amount'.
        Учитывает рыночную цену, параметры стратегии и ордербук.

        Args:
            market: Dictionary containing current market data, expected to have a "price" key.
            current_params: Dictionary of current strategy parameters.
            capital: The available capital for trading.
            step: The current step or iteration in the trading loop.
            orderbook_imbalance: A metric indicating buy/sell pressure from the orderbook.
            orderbook_delta_volume: A metric indicating recent volume changes in the orderbook.
        Returns:
            A dictionary specifying the trading action ("buy" or "sell") and the calculated amount.
        """
        price: float = market.get("price", 100.0)
        # Safely get max_risk_per_trade, default to 0.05 if not found
        max_risk: float = current_params.get("max_risk_per_trade", 0.05)

        # Простейшая эвристика: если ожидаемая доходность положительна – buy, иначе sell.
        # Это можно заменить более сложной логикой в будущем.
        # Ensure config.expected_return_rate exists or provide a default
        expected_return_rate: float = getattr(config, 'expected_return_rate', 0.01) # Default to 1% if not in config
        expected_return: float = price * expected_return_rate
        side: str = "buy" if expected_return > price * 0.001 else "sell" # 0.1% threshold for decision

        # Базовый размер позиции: доля капитала, делённая на цену
        # Ensure price is not zero to avoid division by zero
        amount: float = (capital * max_risk) / price if price > 0 else 0.0

        # --- Корректировка по ордербуку ---
        # Если imbalance сильно против нашего направления – уменьшаем позицию.
        if side == "buy" and orderbook_imbalance < -0.1:
            logger.debug(
                f"[{self.node_id}] Orderbook: strong sell pressure (imbalance={orderbook_imbalance:.2f}), reducing buy amount"
            )
            amount *= 0.6
        elif side == "sell" and orderbook_imbalance > 0.1:
            logger.debug(
                f"[{self.node_id}] Orderbook: strong buy pressure (imbalance={orderbook_imbalance:.2f}), reducing sell amount"
            )
            amount *= 0.6

        # Защита от слишком маленьких или отрицательных значений
        amount = max(0.0, amount)

        return {
            "action": side,
            "amount": amount,
        }