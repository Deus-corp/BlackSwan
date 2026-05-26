"""Thread-safe LLM mutation metrics tracking with optional Prometheus integration."""

from __future__ import annotations

import logging
import math
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore[assignment]
    Gauge = None  # type: ignore[assignment]


class _NoopMetric:
    """Fallback metric object used when prometheus_client is unavailable."""

    def inc(self, amount: float = 1.0) -> None:
        del amount

    def set(self, value: float) -> None:
        del value


class MutationMetrics:
    """Thread-safe manager for LLM mutation statistics and Prometheus metrics."""

    def __init__(self, *, namespace: str = "swarm") -> None:
        self._llm_mutation_count = 0
        self._llm_mutation_total_impact = 0.0
        self._last_capital: Optional[float] = None
        self._lock = threading.RLock()

        self.mutation_counter = self._make_counter(namespace)
        self.mutation_impact_gauge = self._make_gauge(namespace)

    def note_llm_mutation(self, count: int = 1) -> None:
        """Increment mutation counter."""
        safe_count = max(0, int(count))
        if safe_count == 0:
            return

        with self._lock:
            self._llm_mutation_count += safe_count

        self.mutation_counter.inc(safe_count)

    def update_llm_impact(self, current_capital: float) -> None:
        """Update mutation capital impact using current capital delta."""
        capital = self._safe_float(current_capital, float("nan"))
        if not math.isfinite(capital):
            logger.warning("Ignoring non-finite capital for LLM impact update: %r", current_capital)
            return

        with self._lock:
            if self._last_capital is not None:
                self._llm_mutation_total_impact += capital - self._last_capital

            self._last_capital = capital
            avg = self._average_impact_locked()

        self.mutation_impact_gauge.set(avg)

    def reset(self) -> None:
        """Reset in-memory mutation statistics.

        Prometheus counters are monotonic and are not reset.
        """
        with self._lock:
            self._llm_mutation_count = 0
            self._llm_mutation_total_impact = 0.0
            self._last_capital = None

        self.mutation_impact_gauge.set(0.0)

    def get_llm_stats(self) -> tuple[int, float]:
        """Return (total_mutations, average_impact)."""
        with self._lock:
            return self._llm_mutation_count, self._average_impact_locked()

    def to_dict(self) -> dict[str, Any]:
        """Return serializable mutation metrics state."""
        with self._lock:
            return {
                "llm_mutation_count": self._llm_mutation_count,
                "llm_mutation_total_impact": self._llm_mutation_total_impact,
                "llm_mutation_average_impact": self._average_impact_locked(),
                "last_capital": self._last_capital,
            }

    def _average_impact_locked(self) -> float:
        if self._llm_mutation_count <= 0:
            return 0.0
        return self._llm_mutation_total_impact / self._llm_mutation_count

    @staticmethod
    def _make_counter(namespace: str) -> Any:
        if Counter is None:
            return _NoopMetric()

        try:
            return Counter(
                f"{namespace}_mutations_total",
                "Total number of LLM mutations across all nodes",
            )
        except ValueError:
            logger.debug("Prometheus counter already registered; using noop local handle.", exc_info=True)
            return _NoopMetric()

    @staticmethod
    def _make_gauge(namespace: str) -> Any:
        if Gauge is None:
            return _NoopMetric()

        try:
            return Gauge(
                f"{namespace}_mutation_impact",
                "Average impact of LLM mutations on capital",
            )
        except ValueError:
            logger.debug("Prometheus gauge already registered; using noop local handle.", exc_info=True)
            return _NoopMetric()

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


mutation_metrics = MutationMetrics()

note_llm_mutation = mutation_metrics.note_llm_mutation
update_llm_impact = mutation_metrics.update_llm_impact
get_llm_stats = mutation_metrics.get_llm_stats