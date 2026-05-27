#!/usr/bin/env python3
"""Generic survival/viability evaluator for autonomous swarm agents.

This module intentionally avoids being trade-specific. Trading is only one possible
domain where an autonomous node spends resources, takes risks, and receives rewards.

Core concepts:
- resources/capital: available operating budget or energy.
- dq: detection/risk/exposure quotient in range [0, 1].
- liveness: probability-like operational viability in range [0, 1].
- survival score: utility-like scalar used by swarm nodes to decide whether an action
  preserves long-term viability.

Backward-compatible trade methods are preserved:
- evaluate_trade()
- hide()
- expand()
- should_hide()
- should_expand()
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional, TypedDict


class SurvivalConfig(TypedDict, total=False):
    """Configuration parameters for SurvivalEvaluator."""

    lambda_factor: float
    min_p_liveness: float
    max_dq: float
    trade_risk_increase: float
    hide_cost_factor: float
    expand_cost: float
    hide_dq_reduction: float
    expand_liveness_increase: float

    # Generic aliases/newer knobs.
    action_risk_increase: float
    mitigate_cost_factor: float
    resource_expansion_cost: float
    mitigate_dq_reduction: float
    expand_viability_increase: float
    min_resources: float
    max_resources_for_score: float
    baseline_detection: float


class SurvivalSnapshot(TypedDict):
    """Serializable survival state snapshot."""

    dq: float
    liveness: float
    lambda_factor: float
    survival_score: float
    timestamp: float


class ActionEvaluation(TypedDict):
    """Structured result for generic action evaluation."""

    approved: bool
    score: float
    projected_resources: float
    projected_dq: float
    projected_liveness: float
    reason: str


@dataclass(frozen=True, slots=True)
class ActionImpact:
    """Generic action impact on an autonomous agent's survival state."""

    resource_delta: float = 0.0
    dq_delta: float = 0.0
    liveness_delta: float = 0.0
    min_liveness: float | None = None
    max_dq: float | None = None


class SurvivalEvaluator:
    """Evaluate and update survival metrics for autonomous swarm agents."""

    DEFAULT_CONFIG: SurvivalConfig = {
        "lambda_factor": 0.15,
        "min_p_liveness": 0.5,
        "max_dq": 0.2,
        "trade_risk_increase": 0.002,
        "hide_cost_factor": 0.1,
        "expand_cost": 50.0,
        "hide_dq_reduction": 0.01,
        "expand_liveness_increase": 0.02,
        "action_risk_increase": 0.002,
        "mitigate_cost_factor": 0.1,
        "resource_expansion_cost": 50.0,
        "mitigate_dq_reduction": 0.01,
        "expand_viability_increase": 0.02,
        "min_resources": 0.0,
        "max_resources_for_score": 1e9,
        "baseline_detection": 1e-9,
    }

    def __init__(self, config: Optional[Mapping[str, float]] = None) -> None:
        self.config: SurvivalConfig = self.DEFAULT_CONFIG.copy()

        if config:
            for key, value in config.items():
                if key not in self.config:
                    raise ValueError(
                        f"Unknown configuration key: {key}. "
                        f"Valid keys are: {sorted(self.config.keys())}"
                    )
                self.config[key] = self._safe_float(value, float(self.config[key]))  # type: ignore[literal-required]

        self.dq: float = 0.0
        self.liveness: float = 1.0
        self.lambda_: float = float(self.config["lambda_factor"])

        self._sync_legacy_aliases()

    def compute_survival_score(self, capital: float) -> float:
        """Compute survival score for current evaluator state and provided resources."""
        return self.compute_score(
            resources=capital,
            dq=self.dq,
            liveness=self.liveness,
        )

    def compute_score(self, *, resources: float, dq: float, liveness: float) -> float:
        """Compute survival score for explicit projected state."""
        safe_dq = max(float(self.config["baseline_detection"]), self._clamp01(dq))
        safe_liveness = max(float(self.config["baseline_detection"]), self._clamp01(liveness))
        safe_resources = self._bounded_resources(resources)

        return math.log(safe_liveness / safe_dq) + self.lambda_ * math.log(safe_resources + 1.0)

    def evaluate_action(
        self,
        current_resources: float,
        impact: ActionImpact | Mapping[str, Any],
    ) -> ActionEvaluation:
        """Evaluate a generic action without mutating evaluator state."""
        parsed_impact = self._parse_impact(impact)

        projected_resources = max(
            float(self.config["min_resources"]),
            self._safe_float(current_resources, 0.0) + parsed_impact.resource_delta,
        )
        projected_dq = self._clamp01(self.dq + parsed_impact.dq_delta)
        projected_liveness = self._clamp01(self.liveness + parsed_impact.liveness_delta)

        score = self.compute_score(
            resources=projected_resources,
            dq=projected_dq,
            liveness=projected_liveness,
        )

        max_dq = parsed_impact.max_dq if parsed_impact.max_dq is not None else float(self.config["max_dq"])
        min_liveness = (
            parsed_impact.min_liveness
            if parsed_impact.min_liveness is not None
            else float(self.config["min_p_liveness"])
        )

        if projected_dq > max_dq:
            return {
                "approved": False,
                "score": score,
                "projected_resources": projected_resources,
                "projected_dq": projected_dq,
                "projected_liveness": projected_liveness,
                "reason": "dq_limit_exceeded",
            }

        if projected_liveness < min_liveness:
            return {
                "approved": False,
                "score": score,
                "projected_resources": projected_resources,
                "projected_dq": projected_dq,
                "projected_liveness": projected_liveness,
                "reason": "liveness_below_minimum",
            }

        if projected_resources <= float(self.config["min_resources"]):
            return {
                "approved": False,
                "score": score,
                "projected_resources": projected_resources,
                "projected_dq": projected_dq,
                "projected_liveness": projected_liveness,
                "reason": "resources_depleted",
            }

        return {
            "approved": True,
            "score": score,
            "projected_resources": projected_resources,
            "projected_dq": projected_dq,
            "projected_liveness": projected_liveness,
            "reason": "approved",
        }

    def apply_action(self, impact: ActionImpact | Mapping[str, Any]) -> None:
        """Apply generic action impact to evaluator state."""
        parsed_impact = self._parse_impact(impact)
        self.dq = self._clamp01(self.dq + parsed_impact.dq_delta)
        self.liveness = self._clamp01(self.liveness + parsed_impact.liveness_delta)

    def evaluate_trade(self, current_capital: float, expected_return: float) -> tuple[float, bool]:
        """Backward-compatible trade evaluation.

        Trading is treated as a generic resource action with a small exposure increase.
        This method does not mutate evaluator state.
        """
        impact = ActionImpact(
            resource_delta=self._safe_float(expected_return, 0.0),
            dq_delta=float(self.config["trade_risk_increase"]),
        )
        result = self.evaluate_action(current_capital, impact)
        return result["score"], result["approved"]

    def mitigate_exposure(self, resources: float) -> float:
        """Reduce exposure/dq at a proportional resource cost."""
        safe_resources = self._bounded_resources(resources)
        cost = safe_resources * float(self.config["mitigate_cost_factor"])

        self.dq = max(0.0, self.dq - float(self.config["mitigate_dq_reduction"]))
        return max(float(self.config["min_resources"]), safe_resources - cost)

    def hide(self, capital: float) -> float:
        """Legacy alias for mitigate_exposure()."""
        return self.mitigate_exposure(capital)

    def expand_capacity(self, resources: float) -> bool:
        """Increase liveness/viability if enough resources are available."""
        safe_resources = self._safe_float(resources, 0.0)
        cost = float(self.config["resource_expansion_cost"])

        if safe_resources >= cost:
            self.liveness = min(1.0, self.liveness + float(self.config["expand_viability_increase"]))
            return True

        return False

    def expand(self, capital: float) -> bool:
        """Legacy alias for expand_capacity()."""
        return self.expand_capacity(capital)

    def should_mitigate_exposure(self) -> bool:
        """Recommend exposure mitigation when dq approaches configured maximum."""
        return self.dq > float(self.config["max_dq"]) * 0.7

    def should_hide(self) -> bool:
        """Legacy alias for should_mitigate_exposure()."""
        return self.should_mitigate_exposure()

    def should_expand_capacity(self) -> bool:
        """Recommend capacity expansion when liveness is below healthy range."""
        return self.liveness < 0.9

    def should_expand(self) -> bool:
        """Legacy alias for should_expand_capacity()."""
        return self.should_expand_capacity()

    def update_metrics(
        self,
        *,
        dq_delta: float = 0.0,
        liveness_delta: float = 0.0,
        dq: float | None = None,
        liveness: float | None = None,
    ) -> None:
        """Update survival metrics directly or by delta."""
        if dq is not None:
            self.dq = self._clamp01(dq)
        else:
            self.dq = self._clamp01(self.dq + dq_delta)

        if liveness is not None:
            self.liveness = self._clamp01(liveness)
        else:
            self.liveness = self._clamp01(self.liveness + liveness_delta)

    def snapshot(self, resources: float = 0.0) -> SurvivalSnapshot:
        """Return serializable survival state."""
        return {
            "dq": self.dq,
            "liveness": self.liveness,
            "lambda_factor": self.lambda_,
            "survival_score": self.compute_survival_score(resources),
            "timestamp": time.time(),
        }

    def reset(self, *, dq: float = 0.0, liveness: float = 1.0) -> None:
        """Reset evaluator state."""
        self.dq = self._clamp01(dq)
        self.liveness = self._clamp01(liveness)

    def to_dict(self, resources: float = 0.0) -> dict[str, Any]:
        """Return full serializable state including config."""
        return {
            "state": self.snapshot(resources),
            "config": dict(self.config),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SurvivalEvaluator:
        """Create evaluator from serialized state/config."""
        config = data.get("config", {}) if isinstance(data, Mapping) else {}
        evaluator = cls(config if isinstance(config, Mapping) else None)

        state = data.get("state", {}) if isinstance(data, Mapping) else {}
        if isinstance(state, Mapping):
            evaluator.reset(
                dq=evaluator._safe_float(state.get("dq"), 0.0),
                liveness=evaluator._safe_float(state.get("liveness"), 1.0),
            )

        return evaluator

    def _sync_legacy_aliases(self) -> None:
        """Keep legacy and generic configuration keys in sync."""
        pairs = (
            ("trade_risk_increase", "action_risk_increase"),
            ("hide_cost_factor", "mitigate_cost_factor"),
            ("expand_cost", "resource_expansion_cost"),
            ("hide_dq_reduction", "mitigate_dq_reduction"),
            ("expand_liveness_increase", "expand_viability_increase"),
        )

        for legacy_key, generic_key in pairs:
            legacy_value = self.config.get(legacy_key)
            generic_value = self.config.get(generic_key)

            if legacy_value is None and generic_value is not None:
                self.config[legacy_key] = generic_value  # type: ignore[literal-required]
            elif generic_value is None and legacy_value is not None:
                self.config[generic_key] = legacy_value  # type: ignore[literal-required]
            elif legacy_value is not None:
                self.config[generic_key] = legacy_value  # type: ignore[literal-required]

        self.lambda_ = float(self.config["lambda_factor"])

    def _bounded_resources(self, resources: float) -> float:
        value = self._safe_float(resources, 0.0)
        value = max(float(self.config["min_resources"]), value)
        value = min(float(self.config["max_resources_for_score"]), value)
        return value

    @staticmethod
    def _parse_impact(impact: ActionImpact | Mapping[str, Any]) -> ActionImpact:
        if isinstance(impact, ActionImpact):
            return impact

        if not isinstance(impact, Mapping):
            raise TypeError("impact must be ActionImpact or mapping")

        return ActionImpact(
            resource_delta=SurvivalEvaluator._safe_float(impact.get("resource_delta", impact.get("capital_delta")), 0.0),
            dq_delta=SurvivalEvaluator._safe_float(impact.get("dq_delta"), 0.0),
            liveness_delta=SurvivalEvaluator._safe_float(impact.get("liveness_delta"), 0.0),
            min_liveness=(
                None
                if impact.get("min_liveness") is None
                else SurvivalEvaluator._safe_float(impact.get("min_liveness"), 0.0)
            ),
            max_dq=(
                None
                if impact.get("max_dq") is None
                else SurvivalEvaluator._safe_float(impact.get("max_dq"), 1.0)
            ),
        )

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        return number if math.isfinite(number) else default

    @staticmethod
    def _clamp01(value: float) -> float:
        number = SurvivalEvaluator._safe_float(value, 0.0)
        return max(0.0, min(1.0, number))


if __name__ == "__main__":
    print("=== Survival Objective Simulation ===")

    evaluator = SurvivalEvaluator(
        {
            "lambda_factor": 0.2,
            "max_dq": 0.3,
            "trade_risk_increase": 0.005,
            "expand_cost": 75.0,
            "hide_dq_reduction": 0.015,
        }
    )
    resources = 1000.0

    print(f"Initial config: {evaluator.config}")
    print(f"Initial lambda factor: {evaluator.lambda_}")

    for step in range(20):
        score_before = evaluator.compute_survival_score(resources)
        print(
            f"\nStep {step}: resources={resources:.1f}, "
            f"DQ={evaluator.dq:.3f}, liveness={evaluator.liveness:.3f}, "
            f"score={score_before:.3f}"
        )

        if evaluator.should_mitigate_exposure():
            old_dq = evaluator.dq
            before = resources
            resources = evaluator.mitigate_exposure(resources)
            print(f"  -> Mitigate exposure (DQ {old_dq:.3f} -> {evaluator.dq:.3f}, cost={before - resources:.1f})")

        if evaluator.should_expand_capacity():
            if evaluator.expand_capacity(resources):
                resources -= float(evaluator.config["resource_expansion_cost"])
                print(f"  -> Expand capacity (liveness={evaluator.liveness:.3f})")
            else:
                print("  -> Cannot expand capacity: insufficient resources")

        expected_return = 10.0
        simulated_score, approved = evaluator.evaluate_trade(resources, expected_return)

        if approved:
            resources += expected_return
            evaluator.apply_action({"dq_delta": evaluator.config["trade_risk_increase"]})
            print(
                f"  -> Action APPROVED (score={simulated_score:.3f}). "
                f"Resources={resources:.1f}, DQ={evaluator.dq:.3f}"
            )
        else:
            print(
                f"  -> Action REJECTED (score={simulated_score:.3f}). "
                f"DQ={evaluator.dq:.3f}, liveness={evaluator.liveness:.3f}"
            )
            if resources > 5.0:
                resources -= 1.0
                print("     Minor resource burn while staying cautious.")

    final_score = evaluator.compute_survival_score(resources)
    print("\n--- Simulation End ---")
    print(
        f"Final state: resources={resources:.1f}, DQ={evaluator.dq:.3f}, "
        f"liveness={evaluator.liveness:.3f}, final score={final_score:.3f}"
    )