import numpy as np
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Абстрактный агент."""
    def __init__(self, capital: float, max_risk: float = 0.02):
        self.initial_capital = capital
        self.capital = capital
        self.max_risk = max_risk
        self.history = []  # история капитала

    @abstractmethod
    def decide(self, market_state: dict) -> float:
        """
        Возвращает долю капитала для инвестирования (от 0 до max_risk).
        Положительное значение — лонг, отрицательное — шорт.
        """
        ...

    def update(self, returns: float):
        """Обновляет капитал после движения рынка."""
        self.capital *= (1 + returns)
        self.history.append(self.capital)

class KellyAgent(BaseAgent):
    """Агент, использующий модифицированный критерий Келли."""
    def __init__(self, capital: float, max_risk: float = 0.02, phi: float = 0.25):
        super().__init__(capital, max_risk)
        self.phi = phi
        self.p_success = 0.5  # байесовская оценка вероятности успеха

    def decide(self, market_state: dict) -> float:
        # Упрощённо: используем волатильность как индикатор риска
        vol = market_state.get("volatility_estimate", 0.02)
        # Ожидаемая вероятность успеха адаптируется (заглушка)
        odds = 0.01 / vol if vol > 0 else 1.0  # b ≈ норма прибыли на риск
        kelly_fraction = self.p_success - (1 - self.p_success) / odds * self.phi
        # Ограничиваем долю допустимым риском
        return np.clip(kelly_fraction, 0.0, self.max_risk)

class RandomAgent(BaseAgent):
    """Случайный трейдер (базовый уровень)."""
    def decide(self, market_state: dict) -> float:
        return np.random.uniform(-self.max_risk, self.max_risk)