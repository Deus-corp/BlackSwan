import numpy as np

class MarketEnvironment:
    """Простая модель рынка с геометрическим броуновским движением."""

    def __init__(self, volatility: float = 0.02, drift: float = 0.0):
        """
        Args:
            volatility: стандартное отклонение доходности за шаг
            drift: долгосрочный средний дрейф (0 — случайное блуждание)
        """
        self.volatility = volatility
        self.drift = drift
        self.prices = [1.0]  # начальная цена

    def step(self) -> float:
        """Возвращает новую цену и обновляет историю."""
        last_price = self.prices[-1]
        # Доходность: dS/S = μ*dt + σ*dW, dt=1
        returns = np.random.normal(loc=self.drift, scale=self.volatility)
        new_price = last_price * (1 + returns)
        self.prices.append(new_price)
        return new_price

    def get_state(self) -> dict:
        """Возвращает текущее состояние рынка."""
        return {
            "price": self.prices[-1],
            "volatility_estimate": np.std(self.prices[-100:]) if len(self.prices) >= 100 else self.volatility
        }