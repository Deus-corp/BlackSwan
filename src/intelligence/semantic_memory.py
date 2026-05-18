"""
Semantic Memory (L2) – обобщает закономерности из эпизодической памяти (L1)
в виде простых правил, улучшающих стратегию чемпиона.
"""
from typing import Dict, List, Any # Removed unused 'Tuple'
# Removed unused import 'math'

class SemanticMemory:
    """
    Semantic Memory (L2) – компонент, который выводит и применяет
    обобщенные правила на основе исторических эпизодических записей
    для адаптации параметров стратегии.
    """
    def __init__(self) -> None:
        """
        Инициализирует экземпляр SemanticMemory.
        """
        self.rules: List[Dict[str, Any]] = []  # список правил вида {"condition": {...}, "action": {...}}

    def derive_rules(self, episodic_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Анализирует эпизодические записи и выводит правила:
        Если рыночное условие (volatility, dq) было высоким, то
        рекомендовать изменить параметры (например, уменьшить max_risk_per_trade).
        """
        if len(episodic_records) < 10:
            return []  # недостаточно данных

        rules: List[Dict[str, Any]] = []
        # Группируем записи по диапазонам волатильности
        high_vol = [r for r in episodic_records if r.get("volatility", 0.0) > 0.03]
        low_vol = [r for r in episodic_records if r.get("volatility", 0.0) <= 0.03]

        # Правило 1: При высокой волатильности уменьшить max_risk_per_trade
        if high_vol:
            # Ensure safe division by checking if list is not empty (already done by 'if high_vol')
            avg_risk_high = sum(r["params"].get("max_risk_per_trade", 0.0) for r in high_vol) / len(high_vol)
            rules.append({
                "condition": {"volatility": "high"},
                "action": {"max_risk_per_trade": max(0.01, avg_risk_high * 0.8)}  # уменьшаем на 20%
            })

        # Правило 2: При низкой волатильности можно увеличить max_risk_per_trade
        if low_vol:
            avg_risk_low = sum(r["params"].get("max_risk_per_trade", 0.0) for r in low_vol) / len(low_vol)
            rules.append({
                "condition": {"volatility": "low"},
                "action": {"max_risk_per_trade": min(0.2, avg_risk_low * 1.2)}  # увеличиваем на 20%
            })

        # Правило 3: При высоком DQ снизить phi_llm (осторожность)
        high_dq = [r for r in episodic_records if r.get("dq", 0.0) > 0.3]
        if high_dq:
            avg_phi_high_dq = sum(r["params"].get("phi_llm", 0.0) for r in high_dq) / len(high_dq)
            rules.append({
                "condition": {"dq": "high"},
                "action": {"phi_llm": max(0.05, avg_phi_high_dq * 0.8)}
            })

        self.rules = rules
        return rules

    def apply_rules(self, current_params: Dict[str, Any], market_volatility: float, dq: float) -> Dict[str, Any]:
        """Применяет релевантные правила к текущим параметрам."""
        new_params = dict(current_params)
        for rule in self.rules:
            condition = rule["condition"]
            action = rule["action"]
            # Проверяем условие
            if "volatility" in condition:
                if condition["volatility"] == "high" and market_volatility > 0.03:
                    new_params.update(action)
                elif condition["volatility"] == "low" and market_volatility <= 0.03:
                    new_params.update(action)
            if "dq" in condition:
                if condition["dq"] == "high" and dq > 0.3:
                    new_params.update(action)
        return new_params