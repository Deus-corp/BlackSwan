"""Reusable pytest fixtures for core objects."""
from __future__ import annotations
import pytest
from swarm_config import SwarmConfig

@pytest.fixture
def default_config() -> SwarmConfig:
    """Provides a default SwarmConfig for tests."""
    return SwarmConfig()

@pytest.fixture
def metrics_dict() -> dict:
    """Provides a sample metrics dictionary for tests."""
    return {"accuracy": 0.95, "latency": 10.0}
