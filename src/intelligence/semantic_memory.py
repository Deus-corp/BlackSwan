"""Semantic Memory (L2) – derive and apply strategy adaptation rules."""

from __future__ import annotations

import copy
import math
from typing import Any, Final, TypedDict


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
    """Derive generalized strategy rules from episodic memory and apply them."""

    __slots__ = ("rules",)

    MIN_EPISODIC_RECORDS: Final[int] = 10
    HIGH_VOLATILITY_THRESHOLD: Final[float] = 0.03
    HIGH_DQ_THRESHOLD: Final[float] = 0.3

    RISK_REDUCTION_FACTOR: Final[float] = 0.8
    RISK_INCREASE_FACTOR: Final[float] = 1.2
    PHI_LLM_REDUCTION_FACTOR: Final[float] = 0.8

    MIN_MAX_RISK_PER_TRADE: Final[float] = 0.001
    DEFAULT_MIN_MAX_RISK_PER_TRADE: Final[float] = 0.01
    MAX_MAX_RISK_PER_TRADE: Final[float] = 0.2
    MIN_PHI_LLM: Final[float] = 0.05
    MAX_PHI_LLM: Final[float] = 1.0

    def __init__(self) -> None:
        self.rules: list[StrategyRule] = []

    def derive_rules(self, episodic_records: list[dict[str, Any]]) -> list[StrategyRule]:
        """Derive semantic strategy rules from episodic records."""
        if not isinstance(episodic_records, list):
            raise TypeError("episodic_records must be a list")

        records = [record for record in episodic_records if isinstance(record, dict)]
        if len(records) < self.MIN_EPISODIC_RECORDS:
            self.rules = []
            return []

        high_vol = [
            record
            for record in records
            if self._safe_float(record.get("volatility"), 0.0) > self.HIGH_VOLATILITY_THRESHOLD
        ]
        low_vol = [
            record
            for record in records
            if self._safe_float(record.get("volatility"), 0.0) <= self.HIGH_VOLATILITY_THRESHOLD
        ]
        high_dq = [
            record
            for record in records
            if self._safe_float(record.get("dq"), 0.0) > self.HIGH_DQ_THRESHOLD
        ]

        derived_rules: list[StrategyRule] = []

        high_vol_risk = self._average_param(high_vol, "max_risk_per_trade")
        if high_vol_risk is not None:
            value = self._clamp(
                high_vol_risk * self.RISK_REDUCTION_FACTOR,
                self.MIN_MAX_RISK_PER_TRADE,
                self.MAX_MAX_RISK_PER_TRADE,
            )
            derived_rules.append(
                {
                    "condition": {"volatility": "high"},
                    "action": {"max_risk_per_trade": value},
                }
            )

        low_vol_risk = self._average_param(low_vol, "max_risk_per_trade")
        if low_vol_risk is not None:
            value = self._clamp(
                low_vol_risk * self.RISK_INCREASE_FACTOR,
                self.DEFAULT_MIN_MAX_RISK_PER_TRADE,
                self.MAX_MAX_RISK_PER_TRADE,
            )
            derived_rules.append(
                {
                    "condition": {"volatility": "low"},
                    "action": {"max_risk_per_trade": value},
                }
            )

        high_dq_phi = self._average_param(high_dq, "phi_llm")
        if high_dq_phi is not None:
            value = self._clamp(
                high_dq_phi * self.PHI_LLM_REDUCTION_FACTOR,
                self.MIN_PHI_LLM,
                self.MAX_PHI_LLM,
            )
            derived_rules.append(
                {
                    "condition": {"dq": "high"},
                    "action": {"phi_llm": value},
                }
            )

        self.rules = derived_rules
        return copy.deepcopy(derived_rules)

    def apply_rules(
        self,
        current_params: dict[str, Any],
        market_volatility: float,
        dq: float,
    ) -> dict[str, Any]:
        """Apply matching semantic rules to current strategy parameters."""
        if not isinstance(current_params, dict):
            raise TypeError("current_params must be a dictionary")

        new_params = copy.deepcopy(current_params)
        volatility = self._safe_float(market_volatility, 0.0)
        dq_value = self._safe_float(dq, 0.0)

        for rule in self.rules:
            condition = rule.get("condition", {})
            action = rule.get("action", {})

            if not isinstance(condition, dict) or not isinstance(action, dict):
                continue

            if self._matches(condition, volatility=volatility, dq=dq_value):
                self._apply_action(new_params, action)

        return new_params

    def clear_rules(self) -> None:
        """Remove all derived semantic rules."""
        self.rules.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize semantic memory state."""
        return {
            "rules": copy.deepcopy(self.rules),
            "thresholds": {
                "high_volatility": self.HIGH_VOLATILITY_THRESHOLD,
                "high_dq": self.HIGH_DQ_THRESHOLD,
            },
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Load semantic memory state from a dictionary."""
        if not isinstance(data, dict):
            raise TypeError("data must be a dictionary")

        rules = data.get("rules", [])
        if not isinstance(rules, list):
            self.rules = []
            return

        normalized: list[StrategyRule] = []
        for rule in rules:
            normalized_rule = self._normalize_rule(rule)
            if normalized_rule is not None:
                normalized.append(normalized_rule)

        self.rules = normalized

    def _matches(self, condition: RuleCondition, *, volatility: float, dq: float) -> bool:
        volatility_condition = condition.get("volatility")
        dq_condition = condition.get("dq")

        matched = False

        if volatility_condition == "high":
            matched = matched or volatility > self.HIGH_VOLATILITY_THRESHOLD
        elif volatility_condition == "low":
            matched = matched or volatility <= self.HIGH_VOLATILITY_THRESHOLD

        if dq_condition == "high":
            matched = matched or dq > self.HIGH_DQ_THRESHOLD
        elif dq_condition == "low":
            matched = matched or dq <= self.HIGH_DQ_THRESHOLD

        return matched

    def _apply_action(self, params: dict[str, Any], action: RuleAction) -> None:
        if "max_risk_per_trade" in action:
            params["max_risk_per_trade"] = self._clamp(
                self._safe_float(action["max_risk_per_trade"], self.DEFAULT_MIN_MAX_RISK_PER_TRADE),
                self.MIN_MAX_RISK_PER_TRADE,
                self.MAX_MAX_RISK_PER_TRADE,
            )

        if "phi_llm" in action:
            params["phi_llm"] = self._clamp(
                self._safe_float(action["phi_llm"], self.MIN_PHI_LLM),
                self.MIN_PHI_LLM,
                self.MAX_PHI_LLM,
            )

    @classmethod
    def _normalize_rule(cls, rule: Any) -> StrategyRule | None:
        if not isinstance(rule, dict):
            return None

        condition = rule.get("condition", {})
        action = rule.get("action", {})
        if not isinstance(condition, dict) or not isinstance(action, dict):
            return None

        normalized_condition: RuleCondition = {}
        if condition.get("volatility") in {"high", "low"}:
            normalized_condition["volatility"] = condition["volatility"]
        if condition.get("dq") in {"high", "low"}:
            normalized_condition["dq"] = condition["dq"]

        normalized_action: RuleAction = {}
        if "max_risk_per_trade" in action:
            normalized_action["max_risk_per_trade"] = cls._clamp(
                cls._safe_float(action.get("max_risk_per_trade"), cls.DEFAULT_MIN_MAX_RISK_PER_TRADE),
                cls.MIN_MAX_RISK_PER_TRADE,
                cls.MAX_MAX_RISK_PER_TRADE,
            )
        if "phi_llm" in action:
            normalized_action["phi_llm"] = cls._clamp(
                cls._safe_float(action.get("phi_llm"), cls.MIN_PHI_LLM),
                cls.MIN_PHI_LLM,
                cls.MAX_PHI_LLM,
            )

        if not normalized_condition or not normalized_action:
            return None

        return {
            "condition": normalized_condition,
            "action": normalized_action,
        }

    @classmethod
    def _average_param(cls, records: list[dict[str, Any]], param_name: str) -> float | None:
        values: list[float] = []

        for record in records:
            params = record.get("params", {})
            if not isinstance(params, dict) or param_name not in params:
                continue

            value = cls._safe_float(params.get(param_name), float("nan"))
            if math.isfinite(value):
                values.append(value)

        if not values:
            return None

        return math.fsum(values) / len(values)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        return number if math.isfinite(number) else default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))