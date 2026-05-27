#!/usr/bin/env python3
"""Generic curiosity engine for autonomous BlackSwan swarms.

The curiosity engine detects surprise in a stream of observations and generates
bounded exploratory hypotheses for later evaluation.

It is intentionally not trading-specific:
- observations can be market prices, security finding counts, latency, error rates,
  memory novelty, simulation outcomes, or any numeric signal.
- hypotheses are generic numeric parameter dictionaries.
- the legacy market-data API remains compatible with the current trade swarm.

Backward-compatible behavior:
- update({"price": ...}) returns Optional[dict[str, float]]
- stats() returns hypotheses counters and adoption rate
- last_hypothesis is preserved
"""

from __future__ import annotations

import math
import random
import statistics
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional


DEFAULT_PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    # Generic autonomous-system knobs.
    "risk_tolerance": (0.01, 0.30),
    "exploration_rate": (0.01, 0.70),
    "confidence_floor": (0.01, 0.50),
    "memory_weight": (0.01, 1.00),
    "coordination_weight": (0.01, 1.00),
    "self_improvement_rate": (0.001, 0.25),
    # Trade-compatible knobs expected by existing code paths.
    "max_risk_per_trade": (0.01, 0.15),
    "phi_llm": (0.05, 0.35),
    "trailing_stop_ratio": (0.005, 0.05),
    "momentum_window": (5.0, 60.0),
}

kelly_random_params = None

@dataclass(frozen=True, slots=True)
class SurpriseEvent:
    """Recorded surprise event."""

    signal_name: str
    value: float
    prediction: float
    error: float
    average_surprise: float
    timestamp: float = field(default_factory=time.time)


class CuriosityEngine:
    """Detect surprise and generate bounded exploratory hypotheses."""

    def __init__(
        self,
        window_size: int = 20,
        surprise_threshold: float = 0.5,
        error_average_window: int = 5,
        *,
        param_bounds: Optional[Mapping[str, tuple[float, float]]] = None,
        seed: Optional[int] = None,
        signal_name: str = "price",
        perturbation_low: float = 0.5,
        perturbation_high: float = 1.5,
    ) -> None:
        self.window_size = max(2, int(window_size))
        self.surprise_threshold = max(0.0, float(surprise_threshold))
        self.error_average_window = max(1, int(error_average_window))
        self.signal_name = str(signal_name or "price")

        self.param_bounds = self._normalize_bounds(param_bounds or DEFAULT_PARAM_BOUNDS)
        self.perturbation_low = max(0.0, float(perturbation_low))
        self.perturbation_high = max(self.perturbation_low, float(perturbation_high))

        self._rng = random.Random(seed)

        self.price_history: deque[float] = deque(maxlen=self.window_size)
        self.prediction_errors: deque[float] = deque(maxlen=self.error_average_window)

        self.signal_history: dict[str, deque[float]] = {
            self.signal_name: self.price_history,
        }
        self.error_history: dict[str, deque[float]] = {
            self.signal_name: self.prediction_errors,
        }

        self.hypotheses_tested = 0
        self.hypotheses_adopted = 0
        self.hypotheses_rejected = 0
        self.last_hypothesis: Optional[dict[str, float]] = None
        self.last_surprise: Optional[SurpriseEvent] = None
        self.surprise_events: deque[SurpriseEvent] = deque(maxlen=100)

    def update(self, market_data: Mapping[str, Any]) -> Optional[dict[str, float]]:
        """Legacy-compatible update method using market_data['price'] by default."""
        value = self._extract_signal_value(market_data, self.signal_name)
        if value is None:
            return None

        return self.update_signal(self.signal_name, value)

    def update_signal(self, signal_name: str, value: float) -> Optional[dict[str, float]]:
        """Update a named numeric signal and possibly return a new hypothesis."""
        clean_signal = str(signal_name or self.signal_name).strip() or self.signal_name
        safe_value = self._safe_float(value, float("nan"))

        if not math.isfinite(safe_value):
            return None

        history = self.signal_history.setdefault(clean_signal, deque(maxlen=self.window_size))
        errors = self.error_history.setdefault(clean_signal, deque(maxlen=self.error_average_window))

        hypothesis: Optional[dict[str, float]] = None

        if len(history) >= self.window_size:
            prediction = self._predict_next(history)
            error = self._relative_error(safe_value, prediction)
            errors.append(error)

            if len(errors) >= self.error_average_window:
                average_surprise = sum(errors) / len(errors)

                if average_surprise > self.surprise_threshold:
                    event = SurpriseEvent(
                        signal_name=clean_signal,
                        value=safe_value,
                        prediction=prediction,
                        error=error,
                        average_surprise=average_surprise,
                    )
                    self.last_surprise = event
                    self.surprise_events.append(event)

                    hypothesis = self._generate_hypothesis()
                    hypothesis["_surprise"] = average_surprise
                    hypothesis["_signal"] = clean_signal
                    hypothesis["_generated_at"] = time.time()

                    self.hypotheses_tested += 1
                    self.last_hypothesis = hypothesis
                    errors.clear()

        history.append(safe_value)
        return hypothesis

    def update_many(self, observation: Mapping[str, Any]) -> list[dict[str, float]]:
        """Update all numeric fields in an observation and return generated hypotheses."""
        hypotheses: list[dict[str, float]] = []

        for key, value in observation.items():
            if isinstance(value, bool):
                continue

            number = self._safe_float(value, float("nan"))
            if not math.isfinite(number):
                continue

            hypothesis = self.update_signal(str(key), number)
            if hypothesis is not None:
                hypotheses.append(hypothesis)

        return hypotheses

    def _generate_hypothesis(self, baseline: Optional[Mapping[str, Any]] = None) -> dict[str, float]:
        """Generate a bounded exploratory parameter hypothesis."""
        if baseline is None:
            baseline_params = self._baseline_params()
        else:
            baseline_params = {
                str(key): self._safe_float(value, self._midpoint(str(key)))
                for key, value in baseline.items()
            }

        hypothesis: dict[str, float] = {}

        for key, bounds in self.param_bounds.items():
            low, high = bounds
            original = baseline_params.get(key, self._rng.uniform(low, high))

            if original <= 0:
                perturbed = original + self._rng.uniform(-0.15, 0.15) * (high - low)
            else:
                factor = self._rng.uniform(self.perturbation_low, self.perturbation_high)
                perturbed = original * factor

            # Occasionally jump anywhere in range to escape local neighborhoods.
            if self._rng.random() < 0.10:
                perturbed = self._rng.uniform(low, high)

            hypothesis[key] = self._clamp(key, perturbed)

        return hypothesis

    def generate_hypothesis(self, baseline: Optional[Mapping[str, Any]] = None) -> dict[str, float]:
        """Public hypothesis-generation helper."""
        hypothesis = self._generate_hypothesis(baseline)
        self.hypotheses_tested += 1
        self.last_hypothesis = hypothesis
        return hypothesis

    def report_outcome(self, params: Mapping[str, Any], improved: bool) -> None:
        """Report whether a generated hypothesis improved the target objective."""
        del params

        if improved:
            self.hypotheses_adopted += 1
        else:
            self.hypotheses_rejected += 1

    def stats(self) -> dict[str, float]:
        """Return operational statistics."""
        adoption_rate = self.hypotheses_adopted / float(max(1, self.hypotheses_tested))
        rejection_rate = self.hypotheses_rejected / float(max(1, self.hypotheses_tested))

        return {
            "hypotheses_tested": float(self.hypotheses_tested),
            "hypotheses_adopted": float(self.hypotheses_adopted),
            "hypotheses_rejected": float(self.hypotheses_rejected),
            "adoption_rate": adoption_rate,
            "rejection_rate": rejection_rate,
            "last_surprise": float(self.last_surprise.average_surprise) if self.last_surprise else 0.0,
            "signals_tracked": float(len(self.signal_history)),
        }

    def snapshot(self) -> dict[str, Any]:
        """Return serializable curiosity state."""
        return {
            "stats": self.stats(),
            "last_hypothesis": dict(self.last_hypothesis or {}),
            "last_surprise": (
                {
                    "signal_name": self.last_surprise.signal_name,
                    "value": self.last_surprise.value,
                    "prediction": self.last_surprise.prediction,
                    "error": self.last_surprise.error,
                    "average_surprise": self.last_surprise.average_surprise,
                    "timestamp": self.last_surprise.timestamp,
                }
                if self.last_surprise
                else None
            ),
            "history_lengths": {
                signal: len(history)
                for signal, history in self.signal_history.items()
            },
        }

    def reset(self) -> None:
        """Clear histories and counters while keeping configuration."""
        self.price_history.clear()
        self.prediction_errors.clear()
        self.signal_history = {self.signal_name: self.price_history}
        self.error_history = {self.signal_name: self.prediction_errors}
        self.hypotheses_tested = 0
        self.hypotheses_adopted = 0
        self.hypotheses_rejected = 0
        self.last_hypothesis = None
        self.last_surprise = None
        self.surprise_events.clear()

    def _baseline_params(self) -> dict[str, float]:
        if kelly_random_params is not None:
            try:
                params = kelly_random_params()
                if isinstance(params, dict):
                    return {
                        str(key): self._clamp(str(key), value)
                        for key, value in params.items()
                        if str(key) in self.param_bounds
                    }
            except Exception:
                pass

        return {
            key: self._rng.uniform(low, high)
            for key, (low, high) in self.param_bounds.items()
        }

    @staticmethod
    def _predict_next(history: deque[float]) -> float:
        values = list(history)
        if not values:
            return 0.0

        if len(values) >= 3:
            # Blend moving average with simple linear momentum.
            moving_average = statistics.fmean(values)
            momentum = values[-1] - values[-2]
            return moving_average + 0.25 * momentum

        return statistics.fmean(values)

    @staticmethod
    def _relative_error(value: float, prediction: float) -> float:
        denominator = max(abs(prediction), 1e-9)
        return abs(value - prediction) / denominator

    @staticmethod
    def _extract_signal_value(data: Mapping[str, Any], signal_name: str) -> Optional[float]:
        if not isinstance(data, Mapping):
            return None

        value = data.get(signal_name)
        if value is None and signal_name != "price":
            value = data.get("price")
        if value is None:
            return None

        number = CuriosityEngine._safe_float(value, float("nan"))
        return number if math.isfinite(number) else None

    @staticmethod
    def _normalize_bounds(bounds: Mapping[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
        normalized: dict[str, tuple[float, float]] = {}

        for key, raw_bounds in bounds.items():
            if not isinstance(raw_bounds, (tuple, list)) or len(raw_bounds) != 2:
                continue

            low = CuriosityEngine._safe_float(raw_bounds[0], 0.0)
            high = CuriosityEngine._safe_float(raw_bounds[1], 1.0)

            if not math.isfinite(low) or not math.isfinite(high):
                continue

            if high <= low:
                continue

            normalized[str(key)] = (low, high)

        return normalized or dict(DEFAULT_PARAM_BOUNDS)

    def _midpoint(self, key: str) -> float:
        low, high = self.param_bounds.get(key, (0.0, 1.0))
        return (low + high) / 2.0

    def _clamp(self, key: str, value: Any) -> float:
        low, high = self.param_bounds.get(key, (0.0, 1.0))
        number = self._safe_float(value, low)
        return max(low, min(high, number))

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        return number if math.isfinite(number) else default