#!/usr/bin/env python3
"""
SurvivalEvaluator: Computes the Survival Score using the formula:
U = log(P(Liveness) / P(Detection)) + λ·log(Capital).
It blocks actions that threaten survival.
"""

import math
from typing import Dict, Any, Optional, Tuple

class SurvivalEvaluator:
    """
    Manages an agent's survival metrics, including Detection Quotient (DQ) and Liveness (P(Liveness)).
    It computes a survival score and provides mechanisms for evaluating actions like trading,
    hiding, and expanding, based on their impact on survival.
    """
    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        """
        Initializes the SurvivalEvaluator with default or provided configuration.

        Args:
            config: An optional dictionary to override default configuration parameters.
        """
        # Default parameters
        self.config: Dict[str, float] = {
            "lambda": 0.15,            # Weight for capital in survival score
            "min_p_liveness": 0.5,     # Minimum P(Liveness) for trade approval
            "max_dq": 0.2,             # Maximum Detection Quotient for trade approval
            "trade_risk_increase": 0.002, # DQ increase per trade
            "hide_cost_factor": 0.1,   # Capital percentage cost for hiding
            "expand_cost": 50.0,       # Fixed capital cost for expanding (adding a node)
        }
        if config:
            self.config.update(config)

        # Internal state (in a real system, this would come from GlobalState)
        self.dq: float = 0.0            # Detection Quotient (0..1)
        self.liveness: float = 1.0      # P(Liveness) (0..1)
        self.lambda_: float = self.config["lambda"] # Renamed to avoid Python keyword 'lambda'

    def compute_survival_score(self, capital: float) -> float:
        """
        Computes the survival score 'U' based on the formula:
        U = log(P(Liveness) / P(Detection)) + λ·log(Capital).

        P(Detection) is capped at a minimum value to avoid log(0).
        Capital is adjusted by +1.0 to prevent log(0) if capital is zero.

        Args:
            capital: The current capital of the agent.

        Returns:
            The calculated survival score.
        """
        p_detection: float = max(self.dq, 1e-9) # Ensure P(Detection) is never zero
        p_liveness: float = self.liveness
        # Adjust capital by +1.0 to prevent log(0) if capital is 0
        utility: float = math.log(p_liveness / p_detection) + self.lambda_ * math.log(capital + 1.0)
        return utility

    def evaluate_trade(self, capital: float, expected_return: float) -> Tuple[float, bool]:
        """
        Evaluates a potential trade action based on its impact on DQ and capital.
        It simulates the state changes for calculation by temporarily modifying `self.dq`,
        then reverts it, without committing the change unless the caller approves the trade.

        Args:
            capital: The agent's current capital before the trade.
            expected_return: The expected financial return from the trade.

        Returns:
            A tuple containing:
            - The survival score if the trade were to be executed.
            - A boolean indicating if the trade is approved based on survival thresholds.
        """
        # Calculate the potential new DQ if trade were executed
        potential_new_dq: float = self.dq + self.config["trade_risk_increase"]

        # Handle NaN or Inf capital gracefully
        if math.isnan(capital) or math.isinf(capital):
            capital = 1000.0 # Default to a sensible value

        new_capital: float = capital + expected_return
        
        # Ensure new_capital is not negative before calculating score
        new_capital = max(0.0, new_capital)

        # Temporarily apply the potential DQ for score calculation, preserving original functionality
        original_dq: float = self.dq
        self.dq = potential_new_dq 

        score: float = self.compute_survival_score(new_capital)

        # Revert DQ to its original state immediately after calculation
        self.dq = original_dq

        # Apply soft thresholds for active trading, using the potential new DQ
        approved: bool
        if potential_new_dq > self.config["max_dq"]:
            approved = False
        elif self.liveness < self.config["min_p_liveness"]:
            approved = False
        else:
            approved = True

        # The actual DQ change for the evaluator is only applied by the caller
        # if the trade is approved and executed (as shown in __main__ example).
        return score, approved

    def hide(self, capital: float) -> float:
        """
        Simulates a 'hide' action, reducing DQ at a cost to capital.

        Args:
            capital: The agent's current capital.

        Returns:
            The agent's new capital after the hide action, ensuring it's not negative.
        """
        # Cap maximum capital to avoid overflow in calculations (e.g., very large costs)
        max_cap: float = 1e9  # 1 billion is more than sufficient for a lab swarm
        if capital > max_cap or math.isnan(capital) or math.isinf(capital):
            capital = max_cap

        cost: float = capital * self.config["hide_cost_factor"]
        self.dq = max(0.0, self.dq - 0.01) # Reduce DQ, ensuring it doesn't go below 0
        new_capital: float = capital - cost
        
        # Protect against negative capital
        return max(0.0, new_capital)

    def expand(self, capital: float) -> bool:
        """
        Simulates an 'expand' action, increasing P(Liveness) if enough capital is available.
        This represents adding a new node/resource to improve resilience.

        Args:
            capital: The agent's current capital.

        Returns:
            True if the expansion was successful (sufficient capital), False otherwise.
        """
        if capital >= self.config["expand_cost"]:
            self.liveness = min(1.0, self.liveness + 0.02) # Increase liveness, cap at 1.0
            return True
        return False

    def should_hide(self) -> bool:
        """
        Recommends whether the agent should consider hiding based on current DQ.

        Returns:
            True if DQ is suspiciously high, suggesting a need to hide.
        """
        return self.dq > self.config["max_dq"] * 0.7

    def should_expand(self) -> bool:
        """
        Recommends whether the agent should consider expanding based on current P(Liveness).

        Returns:
            True if liveness is below a certain threshold, suggesting a need to expand.
        """
        # Original threshold was 0.9, preserving that for the recommendation logic.
        return self.liveness < 0.9

# Example Usage
if __name__ == "__main__":
    evaluator = SurvivalEvaluator()
    capital = 1000.0

    print("=== Survival Objective Simulation ===")
    for step in range(20):
        score_before: float = evaluator.compute_survival_score(capital)
        print(f"Step {step}: capital={capital:.1f}, DQ={evaluator.dq:.3f}, liveness={evaluator.liveness:.3f}, score={score_before:.3f}")

        # Recommendation: hide if DQ is high
        if evaluator.should_hide():
            capital = evaluator.hide(capital)
            print("  -> Hide (reducing DQ)")

        # Recommendation: expand if liveness is low
        if evaluator.should_expand():
            if evaluator.expand(capital):
                capital -= evaluator.config["expand_cost"] # Cost applied only if expanded
                print("  -> Expand (increasing liveness)")

        # Simulate a trade with safety check
        expected_return: float = 10.0  # Assume market gives a profit
        new_score, approved = evaluator.evaluate_trade(capital, expected_return)
        if approved:
            capital += expected_return
            evaluator.dq += evaluator.config["trade_risk_increase"]  # Apply actual DQ change
            print(f"  -> Trade approved, new score={new_score:.3f}")
        else:
            print("  -> Trade REJECTED (survival threat)")