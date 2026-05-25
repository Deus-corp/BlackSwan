"""
Semantic Memory (L2) – summarizes patterns from episodic memory (L1)
into rules to improve champion strategy adaptation.
"""
import math
from typing import Dict, List, Any, TypedDict, Final


class RuleCondition(TypedDict, total=False):
    """Condition requirements for a strategy rule."""
    volatility: str
    dq: str


class RuleAction(TypedDict, total=False):
    """Action parameters to update in the strategy."""
    max_risk_per_trade: float
    phi_llm: float


class StrategyRule(TypedDict):
    """Container for semantic memory rules."""
    condition: RuleCondition
    action: RuleAction


class SemanticMemory:
    """
    Semantic Memory (L2) derives and applies generalized rules from 
    episodic records to adapt strategy parameters dynamically.
    """

    __slots__ = ("rules",)

    MIN_EPISODIC_RECORDS: Final[int] = 10
    HIGH_VOLATILITY_THRESHOLD: Final[float] = 0.03
    HIGH_DQ_THRESHOLD: Final[float] = 0.3

    RISK_REDUCTION_FACTOR: Final[float] = 0.8
    RISK_INCREASE_FACTOR: Final[float] = 1.2
    PHI_LLM_REDUCTION_FACTOR: Final[float] = 0.8

    MIN_MAX_RISK_PER_TRADE: Final[float] = 0.01
    MAX_MAX_RISK_PER_TRADE: Final[float] = 0.2
    MIN_PHI_LLM: Final[float] = 0.05

    def __init__(self) -> None:
        self.rules: List[StrategyRule] = []

    def derive_rules(self, episodic_records: List[Dict[str, Any]]) -> List[StrategyRule]:
        """
        Derives rules by analyzing historical records. Updates internal rule set.

        Args:
            episodic_records: List of records containing 'volatility', 'dq', and 'params'.

        Returns:
            The list of newly derived rules.
        """
        if len(episodic_records) < self.MIN_EPISODIC_RECORDS:
            return []

        derived_rules: List[StrategyRule] = []

        high_vol = [r for r in episodic_records if r.get("volatility", 0.0) > self.HIGH_VOLATILITY_THRESHOLD]
        low_vol = [r for r in episodic_records if r.get("volatility", 0.0) <= self.HIGH_VOLATILITY_THRESHOLD]
        high_dq = [r for r in episodic_records if r.get("dq", 0.0) > self.HIGH_DQ_THRESHOLD]

        if high_vol:
            avg = math.fsum(r.get("params", {}).get("max_risk_per_trade", 0.0) for r in high_vol) / len(high_vol)
            val = max(self.MIN_MAX_RISK_PER_TRADE, avg * self.RISK_REDUCTION_FACTOR)
            derived_rules.append({"condition": {"volatility": "high"}, "action": {"max_risk_per_trade": val}})

        if low_vol:
            avg = math.fsum(r.get("params", {}).get("max_risk_per_trade", 0.0) for r in low_vol) / len(low_vol)
            val = min(self.MAX_MAX_RISK_PER_TRADE, avg * self.RISK_INCREASE_FACTOR)
            derived_rules.append({"condition": {"volatility": "low"}, "action": {"max_risk_per_trade": val}})

        if high_dq:
            avg = math.fsum(r.get("params", {}).get("phi_llm", 0.0) for r in high_dq) / len(high_dq)
            val = max(self.MIN_PHI_LLM, avg * self.PHI_LLM_REDUCTION_FACTOR)
            derived_rules.append({"condition": {"dq": "high"}, "action": {"phi_llm": val}})

        self.rules = derived_rules
        return derived_rules

    def apply_rules(self, current_params: Dict[str, Any], market_volatility: float, dq: float) -> Dict[str, Any]:
        """
        Applies semantic rules to current parameters based on market state.
        """
        new_params = current_params.copy()

        for rule in self.rules:
            cond = rule["condition"]
            action = rule["action"]

            vol_cond = cond.get("volatility")
            if (vol_cond == "high" and market_volatility > self.HIGH_VOLATILITY_THRESHOLD) or \
               (vol_cond == "low" and market_volatility <= self.HIGH_VOLATILITY_THRESHOLD):
                new_params.update(action)

            if cond.get("dq") == "high" and dq > self.HIGH_DQ_THRESHOLD:
                new_params.update(action)

        return new_params