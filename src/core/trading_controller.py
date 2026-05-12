"""
TradingController — ончейн-торговля: свопы, авто-конвертация USDC, wrap/unwrap,
принятие решений о входе с учётом ордербука.
"""
from typing import Dict, Optional
from loguru import logger
from swarm_config import config
from adapters.web3_testnet import WETH_ADDRESS, USDC_ADDRESS


class TradingController:
    def __init__(self, node_id: str):
        self.node_id = node_id

    # ------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------
    async def check_and_rebalance(self, adapter) -> bool:
        """
        Проверяет балансы и при необходимости выполняет конвертацию или wrap/unwrap.
        Возвращает True, если была выполнена транзакция.
        """
        if not adapter or not adapter.account:
            return False

        try:
            weth_bal = await adapter._get_token_balance(WETH_ADDRESS)
            eth_wei = await adapter.w3.eth.get_balance(adapter.account.address)
            eth_bal = adapter.w3.from_wei(eth_wei, 'ether')
            usdc_bal = await adapter._get_token_balance(USDC_ADDRESS)

            min_weth = config.trading.min_weth_balance
            min_eth = config.trading.min_eth_balance
            max_usdc = config.trading.max_usdc_balance

            # Приоритет: избыток USDC → покупаем WETH
            if usdc_bal > max_usdc and weth_bal < min_weth:
                logger.info(f"[{self.node_id}] USDC surplus ({usdc_bal}), buying WETH")
                result = await adapter.place_order("buy", 0.002)
                logger.info(f"USDC->WETH swap result: {result}")
                return True

            # Wrap при нехватке WETH
            if weth_bal < min_weth and eth_bal > min_eth + 0.0005:
                logger.info(f"[{self.node_id}] WETH low ({weth_bal}), wrapping 0.0005 ETH")
                await adapter.wrap_eth(0.0005)
                return True

            # Unwrap при нехватке ETH
            if eth_bal < min_eth and weth_bal > min_weth + 0.0005:
                logger.info(f"[{self.node_id}] ETH low ({eth_bal}), unwrapping 0.0005 WETH")
                await adapter.unwrap_weth(0.0005)
                return True

        except Exception as e:
            logger.error(f"[{self.node_id}] Rebalance error: {e}")
        return False

    async def execute_swap(self, adapter, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Выполняет одиночный своп."""
        try:
            result = await adapter.place_order(side, amount, price=price)
            logger.info(f"[{self.node_id}] Swap result: {result}")
            return result
        except Exception as e:
            logger.error(f"[{self.node_id}] Swap exception: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------
    # Принятие торгового решения (вызывается из основного цикла)
    # ------------------------------------------------------------
    def decide_action(
        self,
        market: Dict,
        current_params: Dict[str, float],
        capital: float,
        step: int,
        orderbook_imbalance: float = 0.0,
        orderbook_delta_volume: float = 0.0,
    ) -> Dict:
        """
        Возвращает словарь с ключами 'action' (buy/sell) и 'amount'.
        Учитывает рыночную цену, параметры стратегии и ордербук.
        """
        price = market.get("price", 100.0)
        max_risk = current_params.get("max_risk_per_trade", 0.05)

        # Простейшая эвристика: если ожидаемая доходность положительна – buy, иначе sell.
        # Это можно заменить более сложной логикой в будущем.
        expected_return = price * config.expected_return_rate  # конфиг, аналогичный узлу
        side = "buy" if expected_return > price * 0.001 else "sell"

        # Базовый размер позиции: доля капитала, делённая на цену
        amount = (capital * max_risk) / price

        # --- Корректировка по ордербуку ---
        # Если imbalance сильно против нашего направления – уменьшаем позицию.
        if side == "buy" and orderbook_imbalance < -0.1:
            logger.debug(
                f"[{self.node_id}] Orderbook: strong sell pressure, reducing buy amount"
            )
            amount *= 0.6
        elif side == "sell" and orderbook_imbalance > 0.1:
            logger.debug(
                f"[{self.node_id}] Orderbook: strong buy pressure, reducing sell amount"
            )
            amount *= 0.6

        # Защита от слишком маленьких или отрицательных значений
        amount = max(0.0, amount)

        return {
            "action": side,
            "amount": amount,
        }