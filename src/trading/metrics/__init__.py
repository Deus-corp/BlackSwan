"""Metrics collection module for trading systems.

This module provides centralized access to the MetricsCollector component
used for tracking and evaluating trading swarm health and performance.
"""

from .collector import MetricsCollector

__all__ = ["MetricsCollector"]
