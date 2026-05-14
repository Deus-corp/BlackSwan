"""
Абстрактный интерфейс исполнения сделки.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class ExecutionBackend(ABC):
    @abstractmethod
    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> Dict[str, Any]:
        """
        Возвращает словарь с результатом:
        {
            "success": bool,
            "new_capital": float,
            "tx_hash": str | None,
            "status": str,
            "error": str | None
        }
        """
        ...