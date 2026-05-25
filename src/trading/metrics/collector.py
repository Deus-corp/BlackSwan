"""Collect and aggregate trading metrics."""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class MetricsCollector:
    """A thread-safe-capable collector for aggregating numeric trading metrics."""

    def __init__(self) -> None:
        """Initialize an empty metrics store."""
        self.metrics: Dict[str, List[float]] = {}

    def add_metric(self, name: str, value: float) -> None:
        """
        Add a numerical value to a specified metric category.

        Args:
            name: The identifier for the metric.
            value: The numerical value to append.
        """
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)
        logger.info("Added metric %s with value %s", name, value)

    def get_metrics(self, name: Optional[str] = None) -> Dict[str, List[float]]:
        """
        Retrieve metrics store content.

        Args:
            name: Optional specific metric key to retrieve.

        Returns:
            A dictionary containing the requested metric or all metrics.
        """
        if name:
            return {name: self.metrics.get(name, [])}
        return self.metrics

    def clear_metrics(self) -> None:
        """Clear all stored metrics from the collector."""
        self.metrics = {}
        logger.info("Cleared all metrics")