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
from collections import deque
from typing import Dict, List, Optional, Final

from sim.evolve_kelly import random_params, PARAM_BOUNDS

class CuriosityEngine:
    """
    Manages the detection of market anomalies and generation of new strategy hypotheses.

    The engine tracks market price history, calculates prediction errors using a simple
    moving average, and triggers a hypothesis generation process when the average
    prediction error exceeds a specified surprise threshold. Generated hypotheses
    are perturbed versions of baseline random parameters, bounded by predefined ranges.
    """

    def __init__(self, window_size: int = 20, surprise_threshold: float = 0.5, error_average_window: int = 5) -> None:
        """
        Initializes the CuriosityEngine with specified windows and thresholds.

        Args:
            window_size: Number of historical prices to use for prediction.
            surprise_threshold: Threshold for average prediction error to trigger a hypothesis.
            error_average_window: Number of recent prediction errors to average for surprise detection.
        """
        self.window_size: Final[int] = window_size
        self.surprise_threshold: Final[float] = surprise_threshold
        self.error_average_window: Final[int] = error_average_window

        self.price_history: deque[float] = deque(maxlen=window_size)
        self.prediction_errors: deque[float] = deque(maxlen=error_average_window)
        
        self.hypotheses_tested: int = 0
        self.hypotheses_adopted: int = 0
        self.last_hypothesis: Optional[Dict[str, float]] = None

    def update(self, market_data: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Updates the engine with new market data and potentially generates a new hypothesis.

        Calculates a simple moving average prediction based on window_size, determines the
        relative prediction error, and if the average error exceeds surprise_threshold,
        a new set of randomized strategy parameters is generated.
        """
        price = market_data.get("price", 0.0)
        
        if len(self.price_history) >= self.window_size:
            predicted = sum(self.price_history) / self.window_size
            # Use 1e-9 epsilon to prevent division by zero; high error signals anomaly.
            error = abs(price - predicted) / (predicted + 1e-9)
            self.prediction_errors.append(error)

            if len(self.prediction_errors) == self.error_average_window:
                avg_surprise = sum(self.prediction_errors) / self.error_average_window
                if avg_surprise > self.surprise_threshold:
                    hypothesis = self._generate_hypothesis()
                    self.hypotheses_tested += 1
                    self.last_hypothesis = hypothesis
                    self.prediction_errors.clear()
                    return hypothesis

        self.price_history.append(price)
        return None

    def _generate_hypothesis(self) -> Dict[str, float]:
        """
        Generates a new hypothesis by perturbing baseline random parameters.
        """
        hypothesis = random_params()
        for param_key, original_value in hypothesis.items():
            multiplied_value = original_value * random.uniform(0.5, 1.5)
            min_bound, max_bound = PARAM_BOUNDS[param_key]
            hypothesis[param_key] = max(min_bound, min(max_bound, multiplied_value))
        return hypothesis

    def report_outcome(self, params: Dict[str, float], improved: bool) -> None:
        """
        Reports the outcome of testing a generated hypothesis.

        Args:
            params: The specific parameters that were tested.
            improved: True if the strategy resulted in an improvement.
        """
        if improved:
            self.hypotheses_adopted += 1

    def stats(self) -> Dict[str, float]:
        """
        Returns operational statistics of the curiosity engine.
        """
        adoption_rate = self.hypotheses_adopted / float(max(1, self.hypotheses_tested))
        return {
            "hypotheses_tested": float(self.hypotheses_tested),
            "hypotheses_adopted": float(self.hypotheses_adopted),
            "adoption_rate": adoption_rate
        }