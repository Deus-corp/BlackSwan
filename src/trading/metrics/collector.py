"""Collect and aggregate trading metrics."""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Simple metrics collector for trading operations."""

    def __init__(self) -> None:
        self.metrics: Dict[str, List[float]] = {}

    def add_metric(self, name: str, value: float) -> None:
        """Add a metric value."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)
        logger.info("Added metric %s with value %s", name, value)

    def get_metrics(self, name: Optional[str] = None) -> Dict[str, List[float]]:
        """Retrieve metrics by name or all."""
        if name:
            return {name: self.metrics.get(name, [])}
        return self.metrics

    def clear_metrics(self) -> None:
        """Clear all stored metrics."""
        self.metrics = {}
        logger.info("Cleared all metrics")
