#!/usr/bin/env python3
"""
Curiosity Engine: обнаруживает аномалии рынка (Surprise) и генерирует
исследовательские гипотезы (новые параметры стратегии) для тестирования.
"""
import random
from typing import Optional, Dict, List
from sim.evolve_kelly import random_params, PARAM_BOUNDS

class CuriosityEngine:
    def __init__(self, window_size: int = 20, surprise_threshold: float = 0.5):
        self.window_size = window_size
        self.surprise_threshold = surprise_threshold
        self.price_history: List[float] = []
        self.prediction_errors: List[float] = []
        self.hypotheses_tested = 0
        self.hypotheses_adopted = 0
        self.last_hypothesis: Optional[Dict] = None

    def update(self, market_data: Dict) -> Optional[Dict]:
        price = market_data.get("price", 0.0)
        self.price_history.append(price)

        # Используем доступные данные, даже если окно ещё не заполнено
        recent = self.price_history[-min(self.window_size, len(self.price_history)):]
        if len(recent) < 2:   # недостаточно данных для прогноза
            return None

        predicted = sum(recent) / len(recent)
        error = abs(price - predicted) / (predicted + 1e-9)
        self.prediction_errors.append(error)

        # Скользящее среднее ошибки за последние 5 наблюдений
        recent_errors = self.prediction_errors[-5:]
        avg_surprise = sum(recent_errors) / len(recent_errors)
        if avg_surprise > self.surprise_threshold:
            hypothesis = random_params()
            for k in hypothesis:
                hypothesis[k] *= random.uniform(0.5, 1.5)
                hypothesis[k] = max(PARAM_BOUNDS[k][0], min(PARAM_BOUNDS[k][1], hypothesis[k]))
            self.hypotheses_tested += 1
            self.last_hypothesis = hypothesis
            # сбрасываем ошибки, чтобы не генерировать гипотезы подряд
            self.prediction_errors.clear()
            return hypothesis
        return None

    def report_outcome(self, params: Dict, improved: bool):
        if improved:
            self.hypotheses_adopted += 1

    def stats(self) -> dict:
        return {
            "hypotheses_tested": self.hypotheses_tested,
            "hypotheses_adopted": self.hypotheses_adopted,
            "adoption_rate": self.hypotheses_adopted / max(1, self.hypotheses_tested)
        }