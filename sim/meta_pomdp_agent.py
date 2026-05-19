#!/usr/bin/env python3
"""
Meta-POMDP Agent: dynamically adapts weights for Survival, Capital, Curiosity
based on a Belief State derived from 5 macro-scenarios.

This agent is designed to adjust its strategic focus (risk appetite, exploration
vs. exploitation) in response to perceived market or system conditions.
"""
from typing import Dict, Literal, List, Tuple


class MetaPOMDPAgent:
    """
    Agent that adapts its objective weights (survival, capital, curiosity)
    based on a simplified belief state represented by five predefined scenarios.

    Each scenario is defined by a specific set of weights for three objectives:
    survival, capital accumulation, and curiosity/exploration. The agent's
    `update` method transitions between these scenarios based on input metrics.
    """

    # Define a type alias for the scenario names for better type hinting
    ScenarioName = Literal["safe_expansion", "active_hunting", "stealth_mode", "exploration", "crisis"]

    scenarios: Dict[ScenarioName, Dict[str, float]]
    current_scenario: ScenarioName

    def __init__(self) -> None:
        """
        Initializes the agent with predefined weights for five scenarios
        and sets the initial scenario to "safe_expansion".
        """
        # Five scenarios (Belief States), each with specific objective weights
        self.scenarios = {
            "safe_expansion": {"w_survival": 0.6, "w_capital": 0.3, "w_curiosity": 0.1},
            "active_hunting": {"w_survival": 0.4, "w_capital": 0.5, "w_curiosity": 0.1},
            "stealth_mode": {"w_survival": 0.9, "w_capital": 0.1, "w_curiosity": 0.0},
            "exploration": {"w_survival": 0.4, "w_capital": 0.1, "w_curiosity": 0.5},
            "crisis": {"w_survival": 1.0, "w_capital": 0.0, "w_curiosity": 0.0},
        }
        self.current_scenario = "safe_expansion"

    def update(self, dq: float, liveness: float, capital: float, surprise: float) -> Dict[str, float]:
        """
        Determines the current operational scenario based on input metrics
        and returns the corresponding adapted objective weights.

        The scenario selection is prioritized as follows:
        1. Crisis (if `dq` is high OR `liveness` is low OR `capital` is very low).
           Within crisis, differentiates between full 'crisis' (very low liveness)
           and 'stealth_mode' (other crisis conditions).
        2. Exploration (if `surprise` is high AND `capital` is sufficient AND not in crisis).
        3. Active Hunting (if `capital` is high AND `dq` is low AND not in crisis).
        4. Safe Expansion (default, if no other conditions are met).

        Args:
            dq: Data Quality metric. Higher values indicate worse quality/reliability.
                Range typically 0.0 to 1.0.
            liveness: System liveness/health metric. Higher values indicate better health.
                Range typically 0.0 to 1.0.
            capital: Current capital available to the agent.
                Absolute value, but conditions check against fractional thresholds.
            surprise: Novelty or unexpectedness metric. Higher values indicate more surprise/unpredictability.
                Range typically 0.0 to 1.0.

        Returns:
            A dictionary containing the adapted weights for "w_survival", "w_capital",
            and "w_curiosity" based on the determined `current_scenario`.
        """
        # Determine crisis conditions
        in_crisis: bool = (dq >= 0.8) or (liveness < 0.5) or (capital < 0.1)

        # Determine exploration conditions
        # Exploration is only considered if not already in a crisis state
        should_explore: bool = (surprise > 0.7) and (capital > 0.2) and not in_crisis

        # Determine active hunting conditions
        # Active hunting is only considered if not already in a crisis or exploration state
        should_hunt: bool = (capital > 0.5) and (dq < 0.3) and not in_crisis

        # Prioritized scenario selection
        if in_crisis:
            # Differentiate between full crisis (very low liveness) and cautious stealth mode
            self.current_scenario = "crisis" if liveness < 0.3 else "stealth_mode"
        elif should_explore:
            self.current_scenario = "exploration"
        elif should_hunt:
            self.current_scenario = "active_hunting"
        else:
            self.current_scenario = "safe_expansion"

        return self.scenarios[self.current_scenario]


# Quick test for demonstration
if __name__ == "__main__":
    agent: MetaPOMDPAgent = MetaPOMDPAgent()
    test_states: List[Tuple[float, float, float, float]] = [
        (0.1, 0.9, 0.6, 0.2),  # Expected: active_hunting (capital high, dq low, not crisis)
        (0.85, 0.8, 0.5, 0.1), # Expected: stealth_mode (dq high, but liveness not critical, so not full crisis)
        (0.2, 0.7, 0.3, 0.8),  # Expected: exploration (surprise high, capital > 0.2, not crisis)
        (0.9, 0.2, 0.05, 0.05),# Expected: crisis (dq high OR liveness low OR capital low -> all true here)
        (0.4, 0.8, 0.4, 0.4),  # Expected: safe_expansion (default, no other conditions met)
    ]
    print("--- Meta-POMDP Agent Scenario Testing ---")
    for dq_val, lv_val, cap_val, surp_val in test_states:
        weights: Dict[str, float] = agent.update(dq_val, lv_val, cap_val, surp_val)
        print(
            f"DQ={dq_val:.2f} Liveness={lv_val:.2f} Capital={cap_val:.2f} Surprise={surp_val:.2f} "
            f"-> Scenario: {agent.current_scenario}, Weights: {weights}"
        )