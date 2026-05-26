"""Collect and aggregate numeric trading metrics."""

from __future__ import annotations

import logging
import math
import threading
from statistics import mean
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Thread-safe collector for aggregating numeric trading metrics."""

    def __init__(self, *, max_values_per_metric: int | None = None) -> None:
        self.metrics: dict[str, list[float]] = {}
        self.max_values_per_metric = max_values_per_metric
        self._lock = threading.RLock()

    def add_metric(self, name: str, value: float) -> None:
        """Add a finite numeric value to a metric series."""
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("metric name cannot be empty")

        number = self._safe_float(value, float("nan"))
        if not math.isfinite(number):
            raise ValueError(f"metric value must be finite, got {value!r}")

        with self._lock:
            values = self.metrics.setdefault(clean_name, [])
            values.append(number)

            if self.max_values_per_metric is not None:
                limit = max(1, int(self.max_values_per_metric))
                if len(values) > limit:
                    del values[:-limit]

        logger.debug("Added metric %s=%s", clean_name, number)

    def get_metrics(self, name: Optional[str] = None) -> dict[str, list[float]]:
        """Return a copy of one metric series or all series."""
        with self._lock:
            if name:
                clean_name = str(name).strip()
                return {clean_name: list(self.metrics.get(clean_name, []))}
            return {key: list(values) for key, values in self.metrics.items()}

    def summary(self, name: Optional[str] = None) -> dict[str, dict[str, float | int]]:
        """Return count/min/max/mean/latest summary for one or all metrics."""
        with self._lock:
            selected = (
                {str(name).strip(): self.metrics.get(str(name).strip(), [])}
                if name
                else self.metrics
            )

            return {
                key: self._series_summary(values)
                for key, values in selected.items()
            }

    def latest(self, name: str, default: float | None = None) -> float | None:
        """Return the latest value for a metric."""
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("metric name cannot be empty")

        with self._lock:
            values = self.metrics.get(clean_name, [])
            return values[-1] if values else default

    def clear_metrics(self, name: Optional[str] = None) -> None:
        """Clear one metric series or all stored metrics."""
        with self._lock:
            if name:
                self.metrics.pop(str(name).strip(), None)
                logger.info("Cleared metric %s", name)
            else:
                self.metrics.clear()
                logger.info("Cleared all metrics")

    def to_dict(self) -> dict[str, Any]:
        """Return serializable collector state."""
        return {
            "metrics": self.get_metrics(),
            "summary": self.summary(),
            "max_values_per_metric": self.max_values_per_metric,
        }

    @staticmethod
    def _series_summary(values: list[float]) -> dict[str, float | int]:
        if not values:
            return {
                "count": 0,
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "latest": 0.0,
            }

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": mean(values),
            "latest": values[-1],
        }

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default