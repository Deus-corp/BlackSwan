"""
Global LLM mutation metrics tracking.

This module provides a thread-safe registry for tracking LLM mutation events
and their impact on capital, integrated with Prometheus for observability.
"""

import threading
from typing import Tuple, Optional
from prometheus_client import Counter, Gauge

class MutationMetrics:
    """
    Thread-safe manager for LLM mutation statistics and Prometheus metrics.

    Encapsulates mutation counting and capital impact calculations to provide
    consistent state management across the application.
    """

    def __init__(self) -> None:
        """Initialize counters, gauges, and synchronization primitives."""
        self._llm_mutation_count: int = 0
        self._llm_mutation_total_impact: float = 0.0
        self._last_capital: Optional[float] = None
        self._lock: threading.Lock = threading.Lock()

        self.mutation_counter: Counter = Counter(
            "swarm_mutations_total", "Total number of LLM mutations across all nodes"
        )
        self.mutation_impact_gauge: Gauge = Gauge(
            "swarm_mutation_impact", "Average impact of LLM mutations on capital"
        )

    def note_llm_mutation(self) -> None:
        """Increment mutation counter and update Prometheus metrics."""
        with self._lock:
            self._llm_mutation_count += 1
        self.mutation_counter.inc()

    def update_llm_impact(self, current_capital: float) -> None:
        """
        Update total capital impact and calculate average impact gauge.

        Args:
            current_capital: The current portfolio capital post-mutation.
        """
        with self._lock:
            if self._last_capital is not None:
                self._llm_mutation_total_impact += current_capital - self._last_capital
            self._last_capital = current_capital

            avg: float = (
                self._llm_mutation_total_impact / self._llm_mutation_count
                if self._llm_mutation_count > 0
                else 0.0
            )
            self.mutation_impact_gauge.set(avg)

    def get_llm_stats(self) -> Tuple[int, float]:
        """
        Return the current state of mutation metrics.

        Returns:
            A tuple containing (total_mutations, average_impact).
        """
        with self._lock:
            avg: float = (
                self._llm_mutation_total_impact / self._llm_mutation_count
                if self._llm_mutation_count > 0
                else 0.0
            )
            return self._llm_mutation_count, avg

# Global instance for cross-module access
mutation_metrics: MutationMetrics = MutationMetrics()

# Functional interface for legacy support
note_llm_mutation = mutation_metrics.note_llm_mutation
update_llm_impact = mutation_metrics.update_llm_impact
get_llm_stats = mutation_metrics.get_llm_stats