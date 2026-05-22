#!/usr/bin/env python3
"""
Curiosity Engine: detects market anomalies ("Surprise") and generates
exploratory hypotheses (new strategy parameters) for testing.

It monitors market data, calculates prediction errors based on a simple
moving average, and if a significant "surprise" (average prediction error)
is detected, it proposes new, slightly perturbed parameters for a trading
strategy. These parameters are then reported back for evaluation.
"""
import random
from typing import Optional, Dict, List, Tuple, Union

# Assuming PARAM_BOUNDS is Dict[str, Tuple[float, float]]
# and random_params() returns Dict[str, float]
from sim.evolve_kelly import random_params, PARAM_BOUNDS

class CuriosityEngine:
    """
    Manages the detection of market anomalies and generation of new strategy hypotheses.

    The engine tracks market price history, calculates prediction errors using a simple
    moving average, and triggers a hypothesis generation process when the average
    prediction error exceeds a specified surprise threshold. Generated hypotheses
    are perturbed versions of baseline random parameters, bounded by predefined ranges.

    Attributes:
        window_size (int): The number of recent prices to consider for the moving
                           average prediction of the current price.
        surprise_threshold (float): The average prediction error threshold that must
                                    be exceeded to trigger a new hypothesis generation.
        error_average_window (int): The number of recent prediction errors to average
                                    when checking for "surprise."
        price_history (List[float]): A historical record of observed market prices.
        prediction_errors (List[float]): A historical record of calculated prediction errors.
        hypotheses_tested (int): Counter for the total number of hypotheses generated.
        hypotheses_adopted (int): Counter for the number of hypotheses that led to
                                  improved outcomes when reported back.
        last_hypothesis (Optional[Dict[str, float]]): Stores the most recently generated
                                                      hypothesis, if any.
    """

    def __init__(self, window_size: int = 20, surprise_threshold: float = 0.5, error_average_window: int = 5) -> None:
        """
        Initializes the CuriosityEngine.

        Args:
            window_size (int): The number of historical prices to use for the moving
                               average prediction of the current price.
            surprise_threshold (float): The threshold for the average prediction error
                                        to trigger a new hypothesis.
            error_average_window (int): The number of recent prediction errors to average
                                        when checking for "surprise."
        """
        self.window_size: int = window_size
        self.surprise_threshold: float = surprise_threshold
        self.error_average_window: int = error_average_window
        self.price_history: List[float] = []
        self.prediction_errors: List[float] = []
        self.hypotheses_tested: int = 0
        self.hypotheses_adopted: int = 0
        self.last_hypothesis: Optional[Dict[str, float]] = None

    def update(self, market_data: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Updates the engine with new market data and potentially generates a new hypothesis.

        Calculates a simple moving average prediction based on `window_size` (including
        the current price), determines the relative prediction error, and if the average
        error over `error_average_window` exceeds `surprise_threshold`, a new set of
        randomized strategy parameters is generated as a hypothesis.

        Args:
            market_data (Dict[str, float]): A dictionary containing current market data,
                                            expected to have a 'price' key.

        Returns:
            Optional[Dict[str, float]]: A dictionary of new strategy parameters if a
                                        hypothesis is generated, otherwise None.
        """
        price: float = market_data.get("price", 0.0)
        self.price_history.append(price)

        # Use available data for the moving average, even if the window is not yet full.
        # This calculates a simple moving average of recent prices, including the current one.
        relevant_price_history: List[float] = self.price_history[-min(self.window_size, len(self.price_history)):]

        # Need at least one price to calculate an average for prediction.
        if not relevant_price_history:
            # Not enough data to make a prediction or calculate an error meaningful for surprise.
            return None

        # Predict the "expected" current price based on its own moving average.
        # The error then measures how much the current price deviates from its recent average.
        predicted: float = sum(relevant_price_history) / len(relevant_price_history)
        
        # Calculate relative prediction error.
        # Add a small epsilon to the denominator to prevent division by zero if predicted price is 0.
        # If predicted is near zero, this error can become very large, indicating high surprise.
        error: float = abs(price - predicted) / (predicted + 1e-9)
        self.prediction_errors.append(error)

        # Calculate the moving average of prediction errors to detect "surprise."
        recent_errors: List[float] = self.prediction_errors[-min(self.error_average_window, len(self.prediction_errors)):]
        
        # If there are no recent errors (e.g., at the very start), no surprise can be calculated.
        if not recent_errors:
            return None

        avg_surprise: float = sum(recent_errors) / len(recent_errors)

        if avg_surprise > self.surprise_threshold:
            # Generate a new hypothesis by perturbing baseline random parameters.
            hypothesis: Dict[str, float] = random_params()
            for param_key, original_value in hypothesis.items():
                # Apply a random multiplier to diversify the generated hypothesis.
                multiplied_value: float = original_value * random.uniform(0.5, 1.5)
                # Ensure the new value stays within predefined bounds.
                min_bound: float = PARAM_BOUNDS[param_key][0]
                max_bound: float = PARAM_BOUNDS[param_key][1]
                hypothesis[param_key] = max(min_bound, min(max_bound, multiplied_value))
            
            self.hypotheses_tested += 1
            self.last_hypothesis = hypothesis
            
            # Clear prediction errors to prevent immediate re-triggering of hypotheses
            # on consecutive data points if the anomaly persists. This ensures that
            # a new "surprise" event needs to build up again.
            self.prediction_errors.clear()
            return hypothesis
        return None

    def report_outcome(self, params: Dict[str, float], improved: bool) -> None:
        """
        Reports the outcome of testing a generated hypothesis.

        This method is called externally to inform the engine whether a strategy
        tested with specific parameters resulted in an improvement.

        Args:
            params (Dict[str, float]): The specific parameters that were tested.
                                      (Currently, `params` is not directly used beyond
                                      indicating an outcome for *a* hypothesis).
            improved (bool): True if the strategy with these parameters performed
                             better, False otherwise.
        """
        if improved:
            self.hypotheses_adopted += 1

    def stats(self) -> Dict[str, float]:
        """
        Returns statistics about the engine's operation.

        Returns:
            Dict[str, float]: A dictionary containing:
                              - 'hypotheses_tested': Total number of hypotheses generated.
                              - 'hypotheses_adopted': Total number of hypotheses that led to improvements.
                              - 'adoption_rate': The ratio of adopted hypotheses to tested hypotheses.
                                                Returns 0.0 if no hypotheses have been tested.
        """
        # Ensure division by zero is avoided if no hypotheses have been tested.
        adoption_rate: float = self.hypotheses_adopted / float(max(1, self.hypotheses_tested))
        return {
            "hypotheses_tested": float(self.hypotheses_tested),
            "hypotheses_adopted": float(self.hypotheses_adopted),
            "adoption_rate": adoption_rate
        }