#!/usr/bin/env python3
"""
Meta-POMDP Agent: dynamically adapts weights for Survival, Capital, Curiosity
based on a Belief State derived from 5 macro-scenarios.

This agent is designed to adjust its strategic focus (risk appetite, exploration
vs. exploitation) in response to perceived market or system conditions.
"""
from typing import Dict, Final, Literal, List, Tuple


class MetaPOMDPAgent:
    """
    Agent that adapts its objective weights (survival, capital, curiosity)
    based on a simplified belief state represented by five predefined scenarios.

    Each scenario is defined by a specific set of weights for three objectives:
    survival, capital accumulation, and curiosity/exploration.
    """

    ScenarioName = Literal["safe_expansion", "active_hunting", "stealth_mode", "exploration", "crisis"]

    SCENARIOS: Final[Dict[ScenarioName, Dict[str, float]]] = {
        "safe_expansion": {"w_survival": 0.6, "w_capital": 0.3, "w_curiosity": 0.1},
        "active_hunting": {"w_survival": 0.4, "w_capital": 0.5, "w_curiosity": 0.1},
        "stealth_mode": {"w_survival": 0.9, "w_capital": 0.1, "w_curiosity": 0.0},
        "exploration": {"w_survival": 0.4, "w_capital": 0.1, "w_curiosity": 0.5},
        "crisis": {"w_survival": 1.0, "w_capital": 0.0, "w_curiosity": 0.0},
    }

    def __init__(self) -> None:
        """
        Initializes the agent with the default scenario: 'safe_expansion'.
        """
        self.current_scenario: MetaPOMDPAgent.ScenarioName = "safe_expansion"

    def update(self, dq: float, liveness: float, capital: float, surprise: float) -> Dict[str, float]:
        """
        Determines the current operational scenario based on input metrics.

        Args:
            dq: Data Quality metric (0.0 to 1.0). Higher values = worse quality.
            liveness: System health metric (0.0 to 1.0). Higher = better health.
            capital: Current available capital.
            surprise: Novelty/unexpectedness metric (0.0 to 1.0).

        Returns:
            A dictionary of adapted objective weights for the determined scenario.
        """
        # Logic for determining the operational state based on input telemetry
        is_in_critical_danger: bool = (dq >= 0.8) or (liveness < 0.5) or (capital < 0.1)

        if is_in_critical_danger:
            self.current_scenario = "crisis" if liveness < 0.3 else "stealth_mode"
        elif (surprise > 0.7) and (capital > 0.2):
            self.current_scenario = "exploration"
        elif (capital > 0.5) and (dq < 0.3):
            self.current_scenario = "active_hunting"
        else:
            self.current_scenario = "safe_expansion"

        return self.SCENARIOS[self.current_scenario]


if __name__ == "__main__":
    agent = MetaPOMDPAgent()
    test_states: List[Tuple[float, float, float, float]] = [
        (0.1, 0.9, 0.6, 0.2),  # Expected: active_hunting
        (0.85, 0.8, 0.5, 0.1), # Expected: stealth_mode
        (0.2, 0.7, 0.3, 0.8),  # Expected: exploration
        (0.9, 0.2, 0.05, 0.05),# Expected: crisis
        (0.4, 0.8, 0.4, 0.4),  # Expected: safe_expansion
    ]
    print("--- Meta-POMDP Agent Scenario Testing ---")
    for dq_val, lv_val, cap_val, surp_val in test_states:
        weights = agent.update(dq_val, lv_val, cap_val, surp_val)
        print(
            f"DQ={dq_val:.2f} Liveness={lv_val:.2f} Capital={cap_val:.2f} "
            f"Surprise={surp_val:.2f} -> Scenario: {agent.current_scenario}, "
            f"Weights: {weights}"
        )