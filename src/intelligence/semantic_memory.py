"""
Semantic Memory (L2) – обобщает закономерности из эпизодической памяти (L1)
в виде простых правил, улучшающих стратегию чемпиона.
"""
from typing import Dict, List, Any, Union

class SemanticMemory:
    """
    Semantic Memory (L2) – компонент, который выводит и применяет
    обобщенные правила на основе исторических эпизодических записей
    для адаптации параметров стратегии.

    Основные функции:
    - Анализ эпизодических записей для вывода правил.
    - Применение выведенных правил к текущим параметрам стратегии.
    """

    # --- Константы для логики вывода правил ---
    MIN_EPISODIC_RECORDS: int = 10
    HIGH_VOLATILITY_THRESHOLD: float = 0.03
    HIGH_DQ_THRESHOLD: float = 0.3

    # Факторы изменения параметров
    RISK_REDUCTION_FACTOR: float = 0.8  # Уменьшение на 20%
    RISK_INCREASE_FACTOR: float = 1.2   # Увеличение на 20%
    PHI_LLM_REDUCTION_FACTOR: float = 0.8 # Уменьшение на 20%

    # Минимальные/максимальные значения для параметров
    MIN_MAX_RISK_PER_TRADE: float = 0.01
    MAX_MAX_RISK_PER_TRADE: float = 0.2
    MIN_PHI_LLM: float = 0.05

    def __init__(self) -> None:
        """
        Инициализирует экземпляр SemanticMemory.
        """
        self.rules: List[Dict[str, Any]] = []  # список правил вида {"condition": {...}, "action": {...}}

    def derive_rules(self, episodic_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Анализирует эпизодические записи и выводит правила для адаптации стратегии.

        Правила формируются на основе следующих условий:
        - При высокой волатильности: уменьшить max_risk_per_trade.
        - При низкой волатильности: увеличить max_risk_per_trade.
        - При высоком значении 'dq' (Data Quality): снизить phi_llm (осторожность).

        Args:
            episodic_records: Список исторических записей, каждая из которых содержит
                              рыночные условия (volatility, dq) и параметры стратегии (params).

        Returns:
            Список выведенных правил, каждое правило в виде словаря
            {"condition": {...}, "action": {...}}.
        """
        if len(episodic_records) < self.MIN_EPISODIC_RECORDS:
            return []  # недостаточно данных для вывода значимых правил

        rules: List[Dict[str, Any]] = []

        # Группируем записи по диапазонам волатильности
        high_vol: List[Dict[str, Any]] = [
            r for r in episodic_records if r.get("volatility", 0.0) > self.HIGH_VOLATILITY_THRESHOLD
        ]
        low_vol: List[Dict[str, Any]] = [
            r for r in episodic_records if r.get("volatility", 0.0) <= self.HIGH_VOLATILITY_THRESHOLD
        ]

        # Правило 1: При высокой волатильности уменьшить max_risk_per_trade
        if high_vol:
            # Вычисляем средний max_risk_per_trade в условиях высокой волатильности
            avg_risk_high: float = sum(r["params"].get("max_risk_per_trade", 0.0) for r in high_vol) / len(high_vol)
            new_risk_value: float = max(self.MIN_MAX_RISK_PER_TRADE, avg_risk_high * self.RISK_REDUCTION_FACTOR)
            rules.append({
                "condition": {"volatility": "high"},
                "action": {"max_risk_per_trade": new_risk_value}
            })

        # Правило 2: При низкой волатильности можно увеличить max_risk_per_trade
        if low_vol:
            # Вычисляем средний max_risk_per_trade в условиях низкой волатильности
            avg_risk_low: float = sum(r["params"].get("max_risk_per_trade", 0.0) for r in low_vol) / len(low_vol)
            new_risk_value: float = min(self.MAX_MAX_RISK_PER_TRADE, avg_risk_low * self.RISK_INCREASE_FACTOR)
            rules.append({
                "condition": {"volatility": "low"},
                "action": {"max_risk_per_trade": new_risk_value}
            })

        # Правило 3: При высоком DQ снизить phi_llm (осторожность)
        high_dq: List[Dict[str, Any]] = [
            r for r in episodic_records if r.get("dq", 0.0) > self.HIGH_DQ_THRESHOLD
        ]
        if high_dq:
            # Вычисляем средний phi_llm при высоком DQ
            avg_phi_high_dq: float = sum(r["params"].get("phi_llm", 0.0) for r in high_dq) / len(high_dq)
            new_phi_value: float = max(self.MIN_PHI_LLM, avg_phi_high_dq * self.PHI_LLM_REDUCTION_FACTOR)
            rules.append({
                "condition": {"dq": "high"},
                "action": {"phi_llm": new_phi_value}
            })

        self.rules = rules
        return rules

    def apply_rules(self, current_params: Dict[str, Any], market_volatility: float, dq: float) -> Dict[str, Any]:
        """
        Применяет релевантные выведенные правила к текущим параметрам стратегии.

        Args:
            current_params: Текущие параметры стратегии (например, из StrategyParams.model_dump()).
            market_volatility: Текущее значение рыночной волатильности.
            dq: Текущее значение Data Quality (dq).

        Returns:
            Новый словарь параметров стратегии после применения правил.
        """
        new_params: Dict[str, Any] = dict(current_params)
        for rule in self.rules:
            condition: Dict[str, Any] = rule["condition"]
            action: Dict[str, Any] = rule["action"]

            # Проверяем условие на волатильность
            if "volatility" in condition:
                if condition["volatility"] == "high" and market_volatility > self.HIGH_VOLATILITY_THRESHOLD:
                    new_params.update(action)
                elif condition["volatility"] == "low" and market_volatility <= self.HIGH_VOLATILITY_THRESHOLD:
                    new_params.update(action)

            # Проверяем условие на DQ
            if "dq" in condition:
                if condition["dq"] == "high" and dq > self.HIGH_DQ_THRESHOLD:
                    new_params.update(action)
        return new_params