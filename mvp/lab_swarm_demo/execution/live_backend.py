"""
Исполнение на live/web3 (Sepolia через Uniswap V3).
"""
import logging
from typing import Dict, Any, Optional
from .backend import ExecutionBackend

logger = logging.getLogger(__name__)

WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"


class LiveExecutionBackend(ExecutionBackend):
    def __init__(self, node_id: str, adapter, is_leader_func):
        self.node_id = node_id
        self.adapter = adapter
        self.is_leader_func = is_leader_func   # callable (block_number) -> bool

    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> Dict[str, Any]:
        if not self.adapter or not hasattr(self.adapter, "place_order"):
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": "No adapter",
            }

        # Проверка баланса (как в main_loop)
        if side == "sell":
            try:
                weth_bal = await self.adapter._get_token_balance(WETH_ADDRESS)
                amount = min(amount, weth_bal)
            except Exception as e:
                logger.warning(f"Balance check skipped: {e}")

        if amount <= 0:
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": "Insufficient balance",
            }

        # Проверка лидера
        try:
            block_number = await self.adapter.w3.eth.block_number
            if not self.is_leader_func(block_number):
                return {
                    "success": False,
                    "new_capital": capital,
                    "tx_hash": None,
                    "status": "skipped",
                    "error": "Not leader",
                }
        except Exception as e:
            logger.warning(f"Leader check failed: {e}")

        # Исполнение свопа
        try:
            result = await self.adapter.place_order(side, amount, price=price)
            if result.get("status") == "success":
                # Очень грубое обновление капитала — здесь можно улучшить, взяв точное изменение баланса
                new_capital = capital  # реальный капитал обновится позже через RPC (если нужно)
                return {
                    "success": True,
                    "new_capital": new_capital,
                    "tx_hash": result.get("tx_hash"),
                    "status": "success",
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "new_capital": capital,
                    "tx_hash": result.get("tx_hash"),
                    "status": "failed",
                    "error": result.get("error", "Unknown"),
                }
        except Exception as e:
            logger.error(f"Live swap error: {e}")
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": str(e),
            }