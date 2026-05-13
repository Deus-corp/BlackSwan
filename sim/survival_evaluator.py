#!/usr/bin/env python3
"""
SurvivalEvaluator: вычисляет Survival Score по формуле
U = log(P(Liveness) / P(Detection)) + λ·log(Capital).
Блокирует действия, угрожающие выживанию.
"""

import math
from typing import Dict, Any, Optional

class SurvivalEvaluator:
    def __init__(self, config: Optional[Dict[str, float]] = None):
        # Параметры по умолчанию
        self.config = {
        "lambda": 0.15,
        "min_p_liveness": 0.5,     # было 0.9 – теперь разрешаем торговать даже при сниженной живучести
        "max_dq": 0.2,             # было 0.05 – даём больше свободы, детект-порог выше
        "trade_risk_increase": 0.002,
        "hide_cost_factor": 0.1,
        "expand_cost": 50.0,
        }
        if config:
            self.config.update(config)

        # Внутреннее состояние (в реальной системе бралось бы из GlobalState)
        self.dq = 0.0            # Detection Quotient (0..1)
        self.liveness = 1.0      # P(Liveness) (0..1)
        self.lambda_ = self.config["lambda"]

    def compute_survival_score(self, capital: float) -> float:
        """
        U = log(P(Liveness) / P(Detection)) + λ·log(Capital)
        P(Detection) = max(dq, 1e-9), чтобы избежать log(0)
        """
        p_detection = max(self.dq, 1e-9)
        p_liveness = self.liveness
        utility = math.log(p_liveness / p_detection) + self.lambda_ * math.log(capital + 1.0)
        return utility

    def evaluate_trade(self, capital: float, expected_return: float) -> tuple[float, bool]:
        # Безопасная копия DQ
        new_dq = self.dq + self.config["trade_risk_increase"]
        self.dq = new_dq   # временно применяем для расчёта

        if math.isnan(capital) or math.isinf(capital):
            capital = 1000.0

        new_capital = capital + expected_return
        score = self.compute_survival_score(new_capital)

        # Мягкие пороги для активной торговли
        if new_dq > self.config["max_dq"]:
            approved = False
        elif self.liveness < self.config["min_p_liveness"]:
            approved = False
        else:
            approved = True

        # Возвращаем DQ обратно (реальное изменение будет применено только при одобрении)
        self.dq = self.dq - self.config["trade_risk_increase"]
        return score, approved

    def hide(self, capital: float) -> float:
        # Ограничиваем максимальный капитал, чтобы избежать переполнения
        max_cap = 1e9  # 1 миллиард — более чем достаточно для лабораторного роя
        if capital > max_cap or math.isnan(capital) or math.isinf(capital):
            capital = max_cap
        cost = capital * self.config["hide_cost_factor"]
        self.dq = max(0.0, self.dq - 0.01)
        new_capital = capital - cost
        # Защита от отрицательного капитала
        return max(0.0, new_capital)

    def expand(self, capital: float) -> bool:
        """
        Увеличивает P(Liveness) (добавляет узел).
        Возвращает True, если достаточно капитала.
        """
        if capital >= self.config["expand_cost"]:
            self.liveness = min(1.0, self.liveness + 0.02)
            return True
        return False

    def should_hide(self) -> bool:
        """Рекомендация: стоит ли скрываться (если DQ подозрительно высок)."""
        return self.dq > self.config["max_dq"] * 0.7

    def should_expand(self) -> bool:
        """Рекомендация: стоит ли расширяться (если liveness ниже 0.9)."""
        return self.liveness < 0.9

# Пример использования
if __name__ == "__main__":
    evaluator = SurvivalEvaluator()
    capital = 1000.0

    print("=== Симуляция Survival Objective ===")
    for step in range(20):
        score_before = evaluator.compute_survival_score(capital)
        print(f"Шаг {step}: капитал={capital:.1f}, DQ={evaluator.dq:.3f}, liveness={evaluator.liveness:.3f}, score={score_before:.3f}")

        # Рекомендация: скрываться если DQ высок
        if evaluator.should_hide():
            capital = evaluator.hide(capital)
            print("  -> Hide (снижаем DQ)")

        # Рекомендация: расширяться если liveness низок
        if evaluator.should_expand():
            if evaluator.expand(capital):
                capital -= evaluator.config["expand_cost"]
                print("  -> Expand (повышаем liveness)")

        # Имитация торговли с проверкой безопасности
        expected_return = 10.0  # допустим, рынок даёт прибыль
        new_score, approved = evaluator.evaluate_trade(capital, expected_return)
        if approved:
            capital += expected_return
            evaluator.dq += evaluator.config["trade_risk_increase"]  # применяем изменение DQ
            print(f"  -> Trade одобрена, новый счёт={new_score:.3f}")
        else:
            print("  -> Trade ОТКЛОНЕНА (угроза выживанию)")