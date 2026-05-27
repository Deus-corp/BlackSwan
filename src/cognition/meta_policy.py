#!/usr/bin/env python3
"""Meta-policy agent for adaptive objective weighting across autonomous swarms.

The original Meta-POMDP agent adjusted three trade-era objectives:
survival, capital, and curiosity. This version keeps that API but generalizes
the model to a domain-neutral autonomous system:

- survival: preserve viability and safety.
- resources: preserve/grow available budget, energy, capacity, or capital.
- curiosity: explore unknowns and generate hypotheses.
- coordination: cooperate with other swarms/nodes.
- improvement: invest in self-improvement and code/strategy evolution.

Backward-compatible API:
- update(dq, liveness, capital, surprise) -> dict[str, float]
- current_scenario
- SCENARIOS contains w_survival, w_capital, w_curiosity keys.
"""

from __future__ import annotations

import math
import time
from typing import Any, Final, Literal, Mapping, TypedDict


ScenarioName = Literal[
    "safe_expansion",
    "active_hunting",
    "stealth_mode",
    "exploration",
    "crisis",
    "coordination",
    "self_improvement",
]


class ScenarioWeights(TypedDict, total=False):
    """Objective weights for one macro-scenario."""

    w_survival: float
    w_capital: float
    w_curiosity: float
    w_resources: float
    w_coordination: float
    w_improvement: float


class BeliefState(TypedDict):
    """Normalized belief state for meta-policy selection."""

    dq: float
    liveness: float
    resources: float
    surprise: float
    coordination_pressure: float
    improvement_pressure: float
    timestamp: float


class MetaPOMDPAgent:
    """Adaptive meta-policy selector for autonomous swarm objectives."""

    ScenarioName = ScenarioName

    SCENARIOS: Final[dict[ScenarioName, ScenarioWeights]] = {
        "safe_expansion": {
            "w_survival": 0.55,
            "w_capital": 0.25,
            "w_resources": 0.25,
            "w_curiosity": 0.10,
            "w_coordination": 0.07,
            "w_improvement": 0.03,
        },
        "active_hunting": {
            "w_survival": 0.40,
            "w_capital": 0.42,
            "w_resources": 0.42,
            "w_curiosity": 0.08,
            "w_coordination": 0.05,
            "w_improvement": 0.05,
        },
        "stealth_mode": {
            "w_survival": 0.82,
            "w_capital": 0.08,
            "w_resources": 0.08,
            "w_curiosity": 0.02,
            "w_coordination": 0.06,
            "w_improvement": 0.02,
        },
        "exploration": {
            "w_survival": 0.34,
            "w_capital": 0.08,
            "w_resources": 0.08,
            "w_curiosity": 0.42,
            "w_coordination": 0.06,
            "w_improvement": 0.10,
        },
        "crisis": {
            "w_survival": 0.92,
            "w_capital": 0.03,
            "w_resources": 0.03,
            "w_curiosity": 0.00,
            "w_coordination": 0.04,
            "w_improvement": 0.01,
        },
        "coordination": {
            "w_survival": 0.45,
            "w_capital": 0.15,
            "w_resources": 0.15,
            "w_curiosity": 0.08,
            "w_coordination": 0.25,
            "w_improvement": 0.07,
        },
        "self_improvement": {
            "w_survival": 0.45,
            "w_capital": 0.12,
            "w_resources": 0.12,
            "w_curiosity": 0.13,
            "w_coordination": 0.08,
            "w_improvement": 0.22,
        },
    }

    def __init__(
        self,
        *,
        default_scenario: ScenarioName = "safe_expansion",
        smoothing: float = 0.0,
    ) -> None:
        if default_scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown default scenario: {default_scenario}")

        self.current_scenario: ScenarioName = default_scenario
        self.previous_scenario: ScenarioName = default_scenario
        self.smoothing = max(0.0, min(0.95, float(smoothing)))
        self.last_weights: dict[str, float] = dict(self.SCENARIOS[default_scenario])
        self.last_belief: BeliefState = {
            "dq": 0.0,
            "liveness": 1.0,
            "resources": 1.0,
            "surprise": 0.0,
            "coordination_pressure": 0.0,
            "improvement_pressure": 0.0,
            "timestamp": time.time(),
        }
        self.transition_count = 0

    def update(self, dq: float, liveness: float, capital: float, surprise: float) -> dict[str, float]:
        """Backward-compatible update using trade-era metric names."""
        return self.update_belief(
            {
                "dq": dq,
                "liveness": liveness,
                "resources": capital,
                "surprise": surprise,
            }
        )

    def update_belief(self, metrics: Mapping[str, Any]) -> dict[str, float]:
        """Update belief state and return active objective weights."""
        belief = self._normalize_belief(metrics)
        scenario = self.select_scenario(belief)

        self.previous_scenario = self.current_scenario
        self.current_scenario = scenario

        if self.current_scenario != self.previous_scenario:
            self.transition_count += 1

        raw_weights = dict(self.SCENARIOS[self.current_scenario])
        weights = self._smooth_weights(raw_weights)

        self.last_weights = weights
        self.last_belief = belief
        return dict(weights)

    def select_scenario(self, belief: BeliefState) -> ScenarioName:
        """Select macro-scenario from normalized belief state."""
        dq = belief["dq"]
        liveness = belief["liveness"]
        resources = belief["resources"]
        surprise = belief["surprise"]
        coordination_pressure = belief["coordination_pressure"]
        improvement_pressure = belief["improvement_pressure"]

        critical_danger = dq >= 0.8 or liveness < 0.35 or resources < 0.08
        degraded_safety = dq >= 0.55 or liveness < 0.55

        if critical_danger:
            return "crisis"

        if degraded_safety:
            return "stealth_mode"

        if improvement_pressure > 0.75 and liveness > 0.65 and resources > 0.25:
            return "self_improvement"

        if coordination_pressure > 0.70 and liveness > 0.50:
            return "coordination"

        if surprise > 0.70 and resources > 0.20 and dq < 0.60:
            return "exploration"

        if resources > 0.50 and dq < 0.30 and liveness > 0.65:
            return "active_hunting"

        return "safe_expansion"

    def scenario_weights(self, scenario: ScenarioName | None = None) -> dict[str, float]:
        """Return weights for scenario or current scenario."""
        selected = scenario or self.current_scenario
        if selected not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {selected}")
        return dict(self.SCENARIOS[selected])

    def snapshot(self) -> dict[str, Any]:
        """Return serializable meta-policy state."""
        return {
            "current_scenario": self.current_scenario,
            "previous_scenario": self.previous_scenario,
            "transition_count": self.transition_count,
            "last_weights": dict(self.last_weights),
            "last_belief": dict(self.last_belief),
        }

    def reset(self, scenario: ScenarioName = "safe_expansion") -> None:
        """Reset state to a scenario."""
        if scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")

        self.current_scenario = scenario
        self.previous_scenario = scenario
        self.last_weights = dict(self.SCENARIOS[scenario])
        self.transition_count = 0

    def _normalize_belief(self, metrics: Mapping[str, Any]) -> BeliefState:
        resources_value = (
            metrics.get("resources")
            if "resources" in metrics
            else metrics.get("capital", metrics.get("budget", metrics.get("energy", 1.0)))
        )

        return {
            "dq": self._clamp01(metrics.get("dq", metrics.get("risk", metrics.get("exposure", 0.0)))),
            "liveness": self._clamp01(metrics.get("liveness", metrics.get("viability", metrics.get("health", 1.0)))),
            "resources": self._normalize_resources(resources_value),
            "surprise": self._clamp01(metrics.get("surprise", metrics.get("novelty", metrics.get("anomaly", 0.0)))),
            "coordination_pressure": self._clamp01(
                metrics.get("coordination_pressure", metrics.get("coordination", metrics.get("swarm_pressure", 0.0)))
            ),
            "improvement_pressure": self._clamp01(
                metrics.get("improvement_pressure", metrics.get("improvement", metrics.get("mutation_pressure", 0.0)))
            ),
            "timestamp": time.time(),
        }

    def _smooth_weights(self, weights: Mapping[str, float]) -> dict[str, float]:
        if self.smoothing <= 0.0 or not self.last_weights:
            return dict(weights)

        smoothed: dict[str, float] = {}
        all_keys = set(weights) | set(self.last_weights)

        for key in all_keys:
            old = self.last_weights.get(key, 0.0)
            new = float(weights.get(key, 0.0))
            smoothed[key] = self.smoothing * old + (1.0 - self.smoothing) * new

        return smoothed

    @staticmethod
    def _normalize_resources(value: Any) -> float:
        number = MetaPOMDPAgent._safe_float(value, 1.0)

        if number <= 0.0:
            return 0.0

        if number <= 1.0:
            return number

        # Current trade node often passes absolute capital. Compress to [0, 1]
        # without requiring domain-specific assumptions.
        return max(0.0, min(1.0, math.log1p(number) / math.log1p(1000.0)))

    @staticmethod
    def _clamp01(value: Any) -> float:
        number = MetaPOMDPAgent._safe_float(value, 0.0)
        return max(0.0, min(1.0, number))

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default


if __name__ == "__main__":
    agent = MetaPOMDPAgent()
    test_states = [
        {"dq": 0.1, "liveness": 0.9, "resources": 0.6, "surprise": 0.2},
        {"dq": 0.85, "liveness": 0.8, "resources": 0.5, "surprise": 0.1},
        {"dq": 0.2, "liveness": 0.7, "resources": 0.3, "surprise": 0.8},
        {"dq": 0.9, "liveness": 0.2, "resources": 0.05, "surprise": 0.05},
        {"dq": 0.4, "liveness": 0.8, "resources": 0.4, "surprise": 0.4},
        {"dq": 0.2, "liveness": 0.8, "resources": 0.7, "surprise": 0.3, "improvement_pressure": 0.9},
        {"dq": 0.2, "liveness": 0.8, "resources": 0.7, "surprise": 0.3, "coordination_pressure": 0.9},
    ]

    print("--- Meta-POMDP Agent Scenario Testing ---")
    for state in test_states:
        weights = agent.update_belief(state)
        print(f"{state} -> Scenario: {agent.current_scenario}, Weights: {weights}")