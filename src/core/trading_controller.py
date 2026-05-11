"""
TradingController — инкапсулирует ончейн-торговлю: свопы, авто-конвертация USDC, wrap/unwrap, batching.
"""
from typing import Dict, Optional, List
from loguru import logger
from swarm_config import config
from adapters.web3_testnet import WETH_ADDRESS, USDC_ADDRESS


class TradingController:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.pending_swaps: List[dict] = []   # накопленные свопы для батча

    async def check_and_rebalance(self, adapter) -> bool:
        """
        Проверяет балансы и при необходимости добавляет операции в pending_swaps.
        Возвращает True, если были добавлены операции.
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
                # Не планируем buy, если он уже есть в очереди
                if any(s.get("type") == "buy" for s in self.pending_swaps):
                    logger.debug(f"[{self.node_id}] USDC buy already planned, skipping")
                    return False
                logger.info(f"[{self.node_id}] USDC surplus ({usdc_bal}), planning buy WETH")
                self.pending_swaps.append({
                    "type": "buy",
                    "token_in": USDC_ADDRESS,
                    "token_out": WETH_ADDRESS,
                    "amount": 0.002,  # USDC amount? Нужно пересчитать в amount_in_wei
                    "price": None,
                })
                return True

            # Wrap / Unwrap не добавляем в батч, они остаются отдельными вызовами (по необходимости)
            # Здесь оставим только планирование wrap/unwrap как отдельных немедленных действий
            if weth_bal < min_weth and eth_bal > min_eth + 0.0005:
                logger.info(f"[{self.node_id}] WETH low ({weth_bal}), wrapping 0.0005 ETH")
                await adapter.wrap_eth(0.0005)
                return True
            if eth_bal < min_eth and weth_bal > min_weth + 0.0005:
                logger.info(f"[{self.node_id}] ETH low ({eth_bal}), unwrapping 0.0005 WETH")
                await adapter.unwrap_weth(0.0005)
                return True

        except Exception as e:
            logger.error(f"[{self.node_id}] Rebalance error: {e}")
        return False

    def plan_swap(self, side: str, amount: float, price: Optional[float] = None):
        """Добавляет своп в список pending, заменяя предыдущий sell."""
        # Удаляем все предыдущие sell-свопы, оставляя только последний
        self.pending_swaps = [s for s in self.pending_swaps if s.get("type") != "swap"]
        token_in = WETH_ADDRESS if side == "sell" else USDC_ADDRESS
        token_out = USDC_ADDRESS if side == "sell" else WETH_ADDRESS
        self.pending_swaps.append({
            "type": "swap",
            "side": side,
            "token_in": token_in,
            "token_out": token_out,
            "amount": amount,
            "price": price,
        })

    async def execute_pending_batch(self, adapter) -> dict:
        """
        Выполняет все накопленные свопы батчем (через Multicall).
        Очищает список после выполнения.
        """
        if not self.pending_swaps:
            return {"status": "nothing to execute"}

        # Если только один своп – выполняем одиночный
        if len(self.pending_swaps) == 1:
            swap = self.pending_swaps[0]
            self.pending_swaps.clear()
            if swap["type"] == "swap":
                return await self.execute_swap(adapter, swap.get("side", "sell"), swap["amount"], swap.get("price"))
            elif swap["type"] == "buy":
                return await adapter.place_order("buy", 0.002)

        # Формируем параметры для batch_swap
        batch_params = []
        for swap in self.pending_swaps:
            fee = config.trading.web3_pool_fee
            if swap["type"] == "buy":
                token_in = USDC_ADDRESS
                token_out = WETH_ADDRESS
                # amount_in_wei для USDC (decimals=6)
                amount_in_wei = int(swap["amount"] * 10**6)
                batch_params.append({
                    "token_in": token_in,
                    "token_out": token_out,
                    "fee": fee,
                    "amount_in_wei": amount_in_wei,
                    "amount_out_min": 0,
                })
            elif swap["type"] == "swap":
                side = swap.get("side", "sell")
                if side == "sell":
                    token_in = WETH_ADDRESS
                    token_out = USDC_ADDRESS
                    amount_in_wei = adapter.w3.to_wei(swap["amount"], "ether")
                else:
                    token_in = USDC_ADDRESS
                    token_out = WETH_ADDRESS
                    amount_in_wei = int(swap["amount"] * 10**6)
                batch_params.append({
                    "token_in": token_in,
                    "token_out": token_out,
                    "fee": fee,
                    "amount_in_wei": amount_in_wei,
                    "amount_out_min": 0,
                })

        self.pending_swaps.clear()
        if not batch_params:
            return {"status": "empty after processing"}

        logger.info(f"[{self.node_id}] Executing batch of {len(batch_params)} swaps")
        return await adapter.batch_swap(batch_params)

    async def execute_swap(self, adapter, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Выполняет одиночный своп."""
        try:
            result = await adapter.place_order(side, amount, price=price)
            logger.info(f"[{self.node_id}] Swap result: {result}")
            return result
        except Exception as e:
            logger.error(f"[{self.node_id}] Swap exception: {e}")
            return {"error": str(e)}