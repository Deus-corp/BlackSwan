"""
Semantic Memory (L2) – обобщает закономерности из эпизодической памяти (L1)
в виде простых правил, улучшающих стратегию чемпиона.
"""
import math
from typing import Dict, List, Any, TypedDict


# Define TypedDicts for the rule structure for better type clarity and validation
class RuleCondition(TypedDict, total=False):
    """Defines the structure for a rule's condition."""
    volatility: str  # "high" or "low"
    dq: str  # "high"


class RuleAction(TypedDict, total=False):
    """Defines the structure for a rule's action."""
    max_risk_per_trade: float
    phi_llm: float


class StrategyRule(TypedDict):
    """Defines the structure for a semantic memory rule."""
    condition: RuleCondition
    action: RuleAction


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
        # A list of derived rules, each adhering to the StrategyRule TypedDict structure.
        self.rules: List[StrategyRule] = []

    def derive_rules(self, episodic_records: List[Dict[str, Any]]) -> List[StrategyRule]:
        """
        Анализирует эпизодические записи и выводит правила для адаптации стратегии.

        Правила формируются на основе следующих условий:
        - При высокой волатильности: уменьшить max_risk_per_trade.
        - При низкой волатильности: увеличить max_risk_per_trade.
        - При высоком значении 'dq' (Data Quality): снизить phi_llm (осторожность).

        Args:
            episodic_records: Список исторических записей. Каждая запись ожидается
                              в формате `{"volatility": float, "dq": float, "params": {...}}`.
                              'params' должен содержать "max_risk_per_trade" и "phi_llm".

        Returns:
            Список выведенных правил, каждое правило в виде словаря
            `{"condition": {...}, "action": {...}}` adhering to `StrategyRule` structure.
        """
        if len(episodic_records) < self.MIN_EPISODIC_RECORDS:
            return []  # Недостаточно данных для вывода значимых правил

        derived_rules: List[StrategyRule] = []

        # Группируем записи по диапазонам волатильности
        high_vol_records: List[Dict[str, Any]] = [
            r for r in episodic_records if r.get("volatility", 0.0) > self.HIGH_VOLATILITY_THRESHOLD
        ]
        low_vol_records: List[Dict[str, Any]] = [
            r for r in episodic_records if r.get("volatility", 0.0) <= self.HIGH_VOLATILITY_THRESHOLD
        ]

        # Правило 1: При высокой волатильности уменьшить max_risk_per_trade
        if high_vol_records:
            # Вычисляем средний max_risk_per_trade в условиях высокой волатильности
            # Using math.fsum for potentially better precision with floats.
            total_risk_high: float = math.fsum(r["params"].get("max_risk_per_trade", 0.0) for r in high_vol_records)
            avg_risk_high: float = total_risk_high / len(high_vol_records)
            new_risk_value: float = max(self.MIN_MAX_RISK_PER_TRADE, avg_risk_high * self.RISK_REDUCTION_FACTOR)
            derived_rules.append(
                StrategyRule(condition=RuleCondition(volatility="high"),
                             action=RuleAction(max_risk_per_trade=new_risk_value))
            )

        # Правило 2: При низкой волатильности можно увеличить max_risk_per_trade
        if low_vol_records:
            # Вычисляем средний max_risk_per_trade в условиях низкой волатильности
            total_risk_low: float = math.fsum(r["params"].get("max_risk_per_trade", 0.0) for r in low_vol_records)
            avg_risk_low: float = total_risk_low / len(low_vol_records)
            new_risk_value: float = min(self.MAX_MAX_RISK_PER_TRADE, avg_risk_low * self.RISK_INCREASE_FACTOR)
            derived_rules.append(
                StrategyRule(condition=RuleCondition(volatility="low"),
                             action=RuleAction(max_risk_per_trade=new_risk_value))
            )

        # Правило 3: При высоком DQ снизить phi_llm (осторожность)
        high_dq_records: List[Dict[str, Any]] = [
            r for r in episodic_records if r.get("dq", 0.0) > self.HIGH_DQ_THRESHOLD
        ]
        if high_dq_records:
            # Вычисляем средний phi_llm при высоком DQ
            total_phi_high_dq: float = math.fsum(r["params"].get("phi_llm", 0.0) for r in high_dq_records)
            avg_phi_high_dq: float = total_phi_high_dq / len(high_dq_records)
            new_phi_value: float = max(self.MIN_PHI_LLM, avg_phi_high_dq * self.PHI_LLM_REDUCTION_FACTOR)
            derived_rules.append(
                StrategyRule(condition=RuleCondition(dq="high"),
                             action=RuleAction(phi_llm=new_phi_value))
            )

        self.rules = derived_rules  # Store the newly derived rules
        return derived_rules

    def apply_rules(self, current_params: Dict[str, Any], market_volatility: float, dq: float) -> Dict[str, Any]:
        """
        Применяет релевантные выведенные правила к текущим параметрам стратегии.

        Args:
            current_params: Текущие параметры стратегии (например, из StrategyParams.model_dump()).
                            Ожидается, что содержит ключи, которые могут быть изменены правилами,
                            например, "max_risk_per_trade", "phi_llm".
            market_volatility: Текущее значение рыночной волатильности.
            dq: Текущее значение Data Quality (dq).

        Returns:
            Новый словарь параметров стратегии после применения правил.
        """
        # Create a mutable copy to apply changes
        new_params: Dict[str, Any] = dict(current_params)

        for rule_item in self.rules:
            condition: RuleCondition = rule_item["condition"]
            action: RuleAction = rule_item["action"]

            # Check volatility condition
            if "volatility" in condition:
                if condition["volatility"] == "high" and market_volatility > self.HIGH_VOLATILITY_THRESHOLD:
                    new_params.update(action)
                elif condition["volatility"] == "low" and market_volatility <= self.HIGH_VOLATILITY_THRESHOLD:
                    new_params.update(action)

            # Check DQ condition
            if "dq" in condition:
                if condition["dq"] == "high" and dq > self.HIGH_DQ_THRESHOLD:
                    new_params.update(action)
        return new_params