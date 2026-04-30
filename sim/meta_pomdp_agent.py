#!/usr/bin/env python3
"""
Meta-POMDP Agent: динамически адаптирует веса Survival, Capital, Curiosity
на основе Belief State (5 макросценариев).
"""
from typing import Dict

class MetaPOMDPAgent:
    def __init__(self):
        # Пять сценариев (Belief States)
        self.scenarios = {
            "safe_expansion": {"w_survival": 0.6, "w_capital": 0.3, "w_curiosity": 0.1},
            "active_hunting": {"w_survival": 0.4, "w_capital": 0.5, "w_curiosity": 0.1},
            "stealth_mode":   {"w_survival": 0.9, "w_capital": 0.1, "w_curiosity": 0.0},
            "exploration":    {"w_survival": 0.4, "w_capital": 0.1, "w_curiosity": 0.5},
            "crisis":         {"w_survival": 1.0, "w_capital": 0.0, "w_curiosity": 0.0}
        }
        self.current_scenario = "safe_expansion"

    def update(self, dq: float, liveness: float, capital: float, surprise: float) -> Dict[str, float]:
        """Определяет сценарий и возвращает адаптированные веса."""
        in_crisis = (dq >= 0.8) or (liveness < 0.5) or (capital < 0.1)
        should_explore = (surprise > 0.7) and (capital > 0.2) and not in_crisis
        should_hunt = (capital > 0.5) and (dq < 0.3) and not in_crisis

        if in_crisis:
            self.current_scenario = "crisis" if liveness < 0.3 else "stealth_mode"
        elif should_explore:
            self.current_scenario = "exploration"
        elif should_hunt:
            self.current_scenario = "active_hunting"
        else:
            self.current_scenario = "safe_expansion"

        return self.scenarios[self.current_scenario]

# Быстрый тест
if __name__ == "__main__":
    agent = MetaPOMDPAgent()
    test_states = [
        (0.1, 0.9, 0.6, 0.2),  # active hunting
        (0.85, 0.8, 0.5, 0.1), # stealth mode / crisis
        (0.2, 0.7, 0.3, 0.8),  # exploration
        (0.9, 0.2, 0.05, 0.05),# crisis
    ]
    for dq, lv, cap, surp in test_states:
        weights = agent.update(dq, lv, cap, surp)
        print(f"DQ={dq:.2f} Liveness={lv:.2f} Capital={cap:.2f} Surprise={surp:.2f} -> {agent.current_scenario}: {weights}")