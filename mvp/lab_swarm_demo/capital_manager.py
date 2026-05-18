"""
Capital & Risk Manager – управление капиталом, burn-rate, выживаемость.
"""
import logging
from typing import Dict, Any, Optional # Added Any, Optional

from swarm_config import config

logger = logging.getLogger(__name__)


class CapitalManager:
    """
    Manages the capital, burn rate, and survival status of the swarm.
    Tracks capital, applies burn rate, processes trade results, and evaluates liveness.
    """
    def __init__(self, capital: float = 1000.0):
        self.capital: float = capital
        self.burn_rate: float = config.burn_rate
        self.alert_threshold: float = config.capital_alert_threshold

        # ссылка на survival evaluator будет установлена позже через set_survival()
        self.survival: Optional[Any] = None

    def set_survival(self, survival: Any) -> None: # Added type hint
        """Подключает SurvivalEvaluator для использования в проверках."""
        self.survival = survival

    def burn(self) -> None:
        """Списание капитала за шаг (burn rate)."""
        self.capital -= self.burn_rate
        # Simplification: Ensure capital does not go below zero.
        self.capital = max(0.0, self.capital)

    def apply_trade(self, result: Dict[str, Any]) -> float: # Added specific type hint
        """
        Обрабатывает результат сделки.
        Возвращает прирост капитала (может быть отрицательным).
        """
        # Пока используем простую формулу, как раньше: capital *= (1 + ret) - 1.0
        # ret рассчитывался вне этого менеджера, поэтому здесь только обновление
        # В будущем перенесём расчёт полностью сюда
        return 0.0  # Заглушка

    def is_alive(self) -> bool:
        """
        Checks if the capital is greater than zero, indicating the manager is "alive".
        """
        return self.capital > 0

    def health_snapshot(self) -> Dict[str, float]: # Added specific return type hint
        """
        Returns a dictionary containing key health metrics of the capital manager.
        """
        return {
            "capital": self.capital,
            "burn_rate": self.burn_rate,
            # dq and liveness are from the survival evaluator, if available.
            "dq": self.survival.dq if self.survival else 0.0,
            "liveness": self.survival.liveness if self.survival else 1.0,
        }

    def apply_dq_delta(self, delta: float = 0.001) -> None:
        """Увеличивает DQ при успешной сделке."""
        if self.survival:
            self.survival.dq = min(1.0, self.survival.dq + delta)