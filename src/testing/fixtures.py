"""Reusable pytest fixtures for core objects."""

from __future__ import annotations

from typing import Dict

import pytest
from swarm_config import SwarmConfig

@pytest.fixture
def default_config() -> SwarmConfig:
    """Provides a default SwarmConfig instance for test dependency injection.

    Returns:
        SwarmConfig: An initialized default configuration object.
    """
    return SwarmConfig()

@pytest.fixture
def metrics_dict() -> Dict[str, float]:
    """Provides a standard metrics dictionary structure for testing.

    Returns:
        Dict[str, float]: A dictionary containing default sample metrics.
    """
    return {"accuracy": 0.95, "latency": 10.0}