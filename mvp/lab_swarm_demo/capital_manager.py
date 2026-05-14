"""
Capital & Risk Manager – управление капиталом, burn-rate, выживаемость.
"""
import logging
from typing import Dict
from swarm_config import config

logger = logging.getLogger(__name__)


class CapitalManager:
    def __init__(self, capital: float = 1000.0):
        self.capital = capital
        self.burn_rate = config.burn_rate
        self.alert_threshold = config.capital_alert_threshold

        # ссылка на survival evaluator будет установлена позже через set_survival()
        self.survival = None

    def set_survival(self, survival):
        """Подключает SurvivalEvaluator для использования в проверках."""
        self.survival = survival

    def burn(self) -> None:
        """Списание капитала за шаг (burn rate)."""
        self.capital -= self.burn_rate
        if self.capital <= 0:
            self.capital = 0

    def apply_trade(self, result: Dict) -> float:
        """
        Обрабатывает результат сделки.
        Возвращает прирост капитала (может быть отрицательным).
        """
        # Пока используем простую формулу, как раньше: capital *= (1 + ret) - 1.0
        # ret рассчитывался вне этого менеджера, поэтому здесь только обновление
        # В будущем перенесём расчёт полностью сюда
        return 0.0  # Заглушка

    def is_alive(self) -> bool:
        return self.capital > 0

    def health_snapshot(self) -> Dict:
        return {
            "capital": self.capital,
            "burn_rate": self.burn_rate,
            "dq": self.survival.dq if self.survival else 0.0,
            "liveness": self.survival.liveness if self.survival else 1.0,
        }

    def apply_dq_delta(self, delta: float = 0.001) -> None:
        """Увеличивает DQ при успешной сделке."""
        if self.survival:
            self.survival.dq = min(1.0, self.survival.dq + delta)