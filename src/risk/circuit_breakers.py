# src/risk/circuit_breakers.py
"""
Каркас для системы управления рисками (risk engine v2).
Пока все проверки разрешают сделки.
"""
import logging

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Базовый автоматический выключатель."""

    def __init__(self, max_daily_loss: float = 5000.0, max_slippage: float = 0.02):
        self.max_daily_loss = max_daily_loss
        self.max_slippage = max_slippage
        self.daily_pnl = 0.0
        self.halted = False

    def pre_trade_check(self, signal: dict, portfolio: dict) -> bool:
        """Проверка перед сделкой. Пока всегда True."""
        if self.halted:
            logger.warning("Circuit breaker halted")
            return False
        # В будущем: проверка экспозиции, волатильности, ликвидности
        return True

    def post_trade_check(self, fill: dict) -> None:
        """Обновление PnL и проверка лимитов после сделки."""
        pnl = fill.get('pnl', 0.0)
        self.daily_pnl += pnl
        if self.daily_pnl < -self.max_daily_loss:
            self.halted = True
            logger.error("Daily loss limit reached! Halting trading.")

    def reset_daily(self):
        """Сброс дневных счётчиков."""
        self.daily_pnl = 0.0
        self.halted = False