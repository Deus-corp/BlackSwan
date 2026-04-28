"""
ROI Dispatcher v2 – байесовское обновление вероятности успеха и динамический φ.
"""

from typing import Tuple, Optional

class ROIDispatcher:
    def __init__(self, config: Optional[dict] = None):
        # Параметры Kelly
        self.max_risk_per_trade = 0.02
        self.phi_base = 0.25
        self.phi_k_sigma = 5.0
        # Байесовский трекер: Beta(alpha, beta)
        self.alpha = 1.0      # успехи + 1
        self.beta = 1.0       # провалы + 1
        if config:
            self.max_risk_per_trade = config.get("max_risk_per_trade", self.max_risk_per_trade)
            self.phi_base = config.get("phi_llm", self.phi_base)

    def _estimate_success_probability(self, volatility: float) -> float:
        """Байесовская оценка вероятности успеха."""
        # Априорная оценка на основе волатильности
        prior = max(0.4, 0.55 - volatility * 2.5)
        # Апостериорное среднее Beta-распределения
        posterior = self.alpha / (self.alpha + self.beta)
        # Смешиваем: 70% априор, 30% история (пока мало данных)
        return 0.7 * prior + 0.3 * posterior

    def _estimate_odds(self, volatility: float) -> float:
        if volatility <= 0:
            return 1.0
        return 0.02 / volatility

    def _dynamic_phi(self, volatility: float) -> float:
        return min(0.5, self.phi_base * (1.0 + self.phi_k_sigma * volatility))

    def evaluate(self, market_state: dict, capital: float) -> Tuple[float, float]:
        vol = market_state.get('volatility_estimate', 0.02)
        p = self._estimate_success_probability(vol)
        b = self._estimate_odds(vol)
        phi = self._dynamic_phi(vol)

        if b <= 0:
            f_star = 0.0
        else:
            f_star = p - (1.0 - p) / b * phi
        approved = max(0.0, min(f_star, self.max_risk_per_trade))
        survival_score = 1.0
        return approved, survival_score

    def update(self, success: bool):
        """Вызывать после каждой сделки для обучения."""
        if success:
            self.alpha += 1
        else:
            self.beta += 1