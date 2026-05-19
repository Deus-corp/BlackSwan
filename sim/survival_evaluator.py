#!/usr/bin/env python3
"""
SurvivalEvaluator: Computes the Survival Score using the formula:
U = log(P(Liveness) / P(Detection)) + λ·log(Capital).
It blocks actions that threaten survival.
"""

import math
from typing import Dict, Any, Optional, Tuple, TypedDict

# Define a TypedDict for the configuration to provide better type safety and clarity.
# `total=False` allows omitting keys when providing a partial configuration update.
class SurvivalConfig(TypedDict, total=False):
    """
    Typed dictionary for SurvivalEvaluator configuration parameters.
    """
    lambda_factor: float          # Weight for capital in survival score (renamed from 'lambda')
    min_p_liveness: float         # Minimum P(Liveness) for trade approval
    max_dq: float                 # Maximum Detection Quotient for trade approval
    trade_risk_increase: float    # DQ increase per trade
    hide_cost_factor: float       # Capital percentage cost for hiding
    expand_cost: float            # Fixed capital cost for expanding (adding a node)
    hide_dq_reduction: float      # Amount DQ is reduced by a hide action
    expand_liveness_increase: float # Amount P(Liveness) is increased by an expand action


class SurvivalEvaluator:
    """
    Manages an agent's survival metrics, including Detection Quotient (DQ) and Liveness (P(Liveness)).
    It computes a survival score and provides mechanisms for evaluating actions like trading,
    hiding, and expanding, based on their impact on survival.

    The survival score 'U' is calculated using the formula:
    U = log(P(Liveness) / P(Detection)) + λ·log(Capital).

    Key actions (trade, hide, expand) are evaluated against configurable thresholds
    to maintain the agent's long-term survival probability.
    """
    
    # Sensible defaults for config parameters. These can be overridden during initialization.
    DEFAULT_CONFIG: SurvivalConfig = {
        "lambda_factor": 0.15,
        "min_p_liveness": 0.5,
        "max_dq": 0.2,
        "trade_risk_increase": 0.002,
        "hide_cost_factor": 0.1,
        "expand_cost": 50.0,
        "hide_dq_reduction": 0.01,
        "expand_liveness_increase": 0.02,
    }

    def __init__(self, config: Optional[Dict[str, float]] = None) -> None:
        """
        Initializes the SurvivalEvaluator with default or provided configuration.

        Args:
            config: An optional dictionary to override default configuration parameters.
                    Keys should match those defined in `SurvivalConfig`.
        
        Raises:
            ValueError: If an unknown configuration key is provided.
        """
        # Initialize config with defaults, then update with any provided overrides.
        # Use a copy of DEFAULT_CONFIG to ensure instance-specific configurations.
        self.config: SurvivalConfig = self.DEFAULT_CONFIG.copy()
        if config:
            # Ensure provided config keys are valid and update them.
            for key, value in config.items():
                if key in self.config:
                    # Mypy might flag this as `TypedDict` key access issues, but it's valid for updates.
                    self.config[key] = value # type: ignore [literal-required]
                else:
                    raise ValueError(f"Unknown configuration key: {key}. Valid keys are: {list(self.config.keys())}")

        # Internal state (in a real system, this would come from GlobalState)
        self.dq: float = 0.0            # Detection Quotient (0..1), represents P(Detection)
        self.liveness: float = 1.0      # P(Liveness) (0..1)
        # Use the configured lambda factor. Renamed from 'lambda' to 'lambda_factor' to avoid Python keyword conflicts.
        self.lambda_: float = self.config["lambda_factor"]

    def compute_survival_score(self, capital: float) -> float:
        """
        Computes the survival score 'U' based on the formula:
        U = log(P(Liveness) / P(Detection)) + λ·log(Capital).

        P(Detection) is capped at a minimum positive value to avoid log(0) and
        represent a non-zero baseline detection probability.
        Capital is adjusted by adding 1.0 to prevent log(0) if capital is zero or negative.

        Args:
            capital: The current capital of the agent.

        Returns:
            The calculated survival score.
        """
        # Ensure P(Detection) (self.dq) is never zero to avoid log(0) issues.
        # A small non-zero value represents an inherent, minimal detectability.
        p_detection: float = max(self.dq, 1e-9) 
        p_liveness: float = self.liveness
        
        # Adjust capital by +1.0 to prevent log(0) if capital is 0 or negative.
        # Ensure capital is non-negative before adding 1.0.
        effective_capital: float = max(0.0, capital) + 1.0
        
        # Calculate the survival score
        survival_score: float = math.log(p_liveness / p_detection) + self.lambda_ * math.log(effective_capital)
        return survival_score

    def evaluate_trade(self, current_capital: float, expected_return: float) -> Tuple[float, bool]:
        """
        Evaluates a potential trade action based on its simulated impact on DQ and capital.
        This method calculates the survival score *as if* the trade were executed,
        but does NOT commit the state changes (`self.dq` or `self.liveness`).
        The caller is responsible for applying the actual state changes if the trade is approved and executed.

        Args:
            current_capital: The agent's current capital before the trade.
            expected_return: The expected financial return (can be negative for a loss) from the trade.

        Returns:
            A tuple containing:
            - The survival score if the trade were to be executed.
            - A boolean indicating if the trade is approved based on internal survival thresholds.
        """
        # Calculate the potential new DQ if trade were executed.
        # This is a simulation for evaluation, so we don't modify self.dq directly yet.
        potential_new_dq: float = self.dq + self.config["trade_risk_increase"]

        # Handle NaN or Inf capital gracefully for calculation purposes.
        # Defaulting to a sensible value for robust simulation, assuming external validation
        # prevents such invalid states from persisting.
        if math.isnan(current_capital) or math.isinf(current_capital):
            current_capital = 1000.0 # A reasonable default to avoid breaking calculations

        # Calculate potential new capital. Ensure it doesn't go negative.
        potential_new_capital: float = max(0.0, current_capital + expected_return)
        
        # --- Simulate temporary state for score calculation ---
        # Temporarily store the current DQ to revert it later.
        # This pattern allows `compute_survival_score` to use the simulated DQ
        # without affecting the evaluator's persistent state.
        original_dq: float = self.dq
        self.dq = potential_new_dq  # Apply the potential DQ for score calculation

        # Compute the survival score with the simulated state.
        simulated_score: float = self.compute_survival_score(potential_new_capital)

        # Revert DQ to its original state immediately after calculation.
        # This is crucial for 'evaluation' methods that only predict outcomes, not commit them.
        self.dq = original_dq
        # --- End simulation ---

        # Apply soft thresholds for active trading, using the potential new DQ.
        approved: bool
        if potential_new_dq > self.config["max_dq"]:
            approved = False
        elif self.liveness < self.config["min_p_liveness"]:
            approved = False
        else:
            approved = True

        return simulated_score, approved

    def hide(self, capital: float) -> float:
        """
        Simulates a 'hide' action, reducing DQ at a cost to capital.
        This method applies the state change for DQ and returns the new capital.

        Args:
            capital: The agent's current capital.

        Returns:
            The agent's new capital after the hide action, ensuring it's not negative.
        """
        # Cap maximum capital to avoid overflow in calculations (e.g., very large costs)
        # and handle invalid inputs. This is a pragmatic limit for simulation stability.
        max_cap: float = 1e9  # 1 billion is generally more than sufficient
        if capital > max_cap or math.isnan(capital) or math.isinf(capital):
            capital = max_cap

        cost: float = capital * self.config["hide_cost_factor"]
        
        # Reduce DQ by a configurable amount, ensuring it doesn't go below 0.
        self.dq = max(0.0, self.dq - self.config["hide_dq_reduction"]) 
        
        new_capital: float = capital - cost
        
        # Protect against negative capital.
        return max(0.0, new_capital)

    def expand(self, capital: float) -> bool:
        """
        Simulates an 'expand' action, increasing P(Liveness) if enough capital is available.
        This represents adding a new node/resource to improve resilience.
        This method applies the state change for liveness if successful.

        Args:
            capital: The agent's current capital.

        Returns:
            True if the expansion was successful (sufficient capital), False otherwise.
        """
        if capital >= self.config["expand_cost"]:
            # Increase liveness by a configurable amount, capping at 1.0 (100% probability).
            self.liveness = min(1.0, self.liveness + self.config["expand_liveness_increase"]) 
            return True
        return False

    def should_hide(self) -> bool:
        """
        Recommends whether the agent should consider hiding based on current DQ.
        A hide action is recommended if DQ is above a certain threshold (e.g., 70% of max_dq),
        suggesting increased detectability. This threshold can be different from the hard limit
        for action approval.

        Returns:
            True if DQ is suspiciously high, suggesting a need to hide.
        """
        return self.dq > self.config["max_dq"] * 0.7

    def should_expand(self) -> bool:
        """
        Recommends whether the agent should consider expanding based on current P(Liveness).
        An expand action is recommended if P(Liveness) is below a certain threshold (e.g., 0.9),
        suggesting a need to improve resilience. This threshold is specific to the recommendation logic.

        Returns:
            True if liveness is below a certain threshold, suggesting a need to expand.
        """
        return self.liveness < 0.9

# Example Usage
if __name__ == "__main__":
    print("=== Survival Objective Simulation ===")
    
    # Custom configuration example for demonstration
    custom_config: Dict[str, float] = {
        "lambda_factor": 0.2,
        "max_dq": 0.3,
        "trade_risk_increase": 0.005,
        "expand_cost": 75.0,
        "hide_dq_reduction": 0.015,
    }
    evaluator = SurvivalEvaluator(custom_config)
    capital: float = 1000.0

    print(f"Initial config: {evaluator.config}")
    print(f"Initial lambda factor: {evaluator.lambda_}")

    for step in range(20):
        score_before: float = evaluator.compute_survival_score(capital)
        print(f"\nStep {step}: capital={capital:.1f}, DQ={evaluator.dq:.3f}, liveness={evaluator.liveness:.3f}, score={score_before:.3f}")

        # Agent decision logic based on recommendations and evaluations
        
        # 1. Consider hiding if DQ is too high
        if evaluator.should_hide():
            old_dq = evaluator.dq
            capital_before_hide = capital
            capital = evaluator.hide(capital)
            cost_of_hide = capital_before_hide - capital
            print(f"  -> Hide (DQ {old_dq:.3f} -> {evaluator.dq:.3f}, cost={cost_of_hide:.1f})")

        # 2. Consider expanding if liveness is low
        if evaluator.should_expand():
            if evaluator.expand(capital):
                # Cost is applied externally as the expand method only checks feasibility and updates liveness
                capital -= evaluator.config["expand_cost"] 
                print(f"  -> Expand (liveness {evaluator.liveness - evaluator.config['expand_liveness_increase']:.3f} -> {evaluator.liveness:.3f}, cost={evaluator.config['expand_cost']:.1f})")
            else:
                print(f"  -> Cannot expand (insufficient capital: {capital:.1f} < {evaluator.config['expand_cost']:.1f})")

        # 3. Evaluate a potential trade
        expected_return: float = 10.0  # Assume market gives a fixed profit for this example
        simulated_score, approved = evaluator.evaluate_trade(capital, expected_return)
        
        if approved:
            capital += expected_return
            # Apply actual DQ change if trade is executed
            evaluator.dq += evaluator.config["trade_risk_increase"]  
            print(f"  -> Trade APPROVED (simulated score={simulated_score:.3f}). Capital: {capital:.1f}, DQ: {evaluator.dq:.3f}")
        else:
            print(f"  -> Trade REJECTED (simulated score={simulated_score:.3f}). Current DQ={evaluator.dq:.3f}, P(Liveness)={evaluator.liveness:.3f}")
            # Provide reasons for rejection
            if evaluator.dq > evaluator.config["max_dq"]:
                print("     (Reason: DQ too high for safe trading)")
            elif evaluator.liveness < evaluator.config["min_p_liveness"]:
                print("     (Reason: P(Liveness) too low for safe trading)")
            
            # Example reactive action: if trade rejected, perhaps burn a small amount of capital
            # to simulate a "wait and see" or "lay low" period if no other actions were taken.
            if not evaluator.should_hide() and not evaluator.should_expand():
                if capital > 5.0: # Arbitrary small cost to avoid negative capital
                    capital -= 1.0
                    print("     (Minor capital burn due to trade rejection - agent staying cautious)")
                else:
                    print("     (Capital too low for even minor burn after rejection)")


    final_score: float = evaluator.compute_survival_score(capital)
    print(f"\n--- Simulation End ---")
    print(f"Final state: capital={capital:.1f}, DQ={evaluator.dq:.3f}, liveness={evaluator.liveness:.3f}, final score={final_score:.3f}")